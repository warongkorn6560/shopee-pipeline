"""
Scene visuals for Flow B.

Provider chain per scene (STORY_IMAGE_PROVIDER):
  auto      maps/photos/portraits/artifacts → Wikimedia, then AI, then card
            "scene" illustrations           → AI, then Wikimedia, then card
  wikimedia Wikimedia Commons, then card
  gateway   Vercel AI Gateway image model, then card
  cards     designed globe cards only

Wikimedia images are limited to public-domain / CC0 / CC BY / CC BY-SA and
always carry an on-screen credit. AI images are capped per video and skipped for
the rest of the run as soon as the Gateway refuses (e.g. free-tier accounts).
"""

from __future__ import annotations

import base64
import io
import re
import threading
from dataclasses import dataclass
from pathlib import Path

import requests

from ..config import (
    ENV, STORY_IMAGE_MODEL, STORY_IMAGE_PROVIDER, STORY_MAX_AI_IMAGES,
)
from ..frames import globe_card

UA = "ShopeePipelineStoryBot/1.0 (https://github.com/warongkorn6560/shopee-pipeline)"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
_OK_LICENSE = re.compile(r"(public domain|^pd|cc0|cc[- ]by(?!.*\bn[cd]\b))", re.I)


@dataclass
class SceneImage:
    path: Path
    credit: str = ""
    provider: str = "card"


class _Budget:
    def __init__(self, limit: int):
        self.limit, self.used, self.disabled = limit, 0, False
        self.lock = threading.Lock()

    def take(self) -> bool:
        with self.lock:
            if self.disabled or self.used >= self.limit:
                return False
            self.used += 1
            return True


def _strip_html(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s or "")).strip()


_STOP = {"with", "from", "that", "this", "showing", "old", "the", "and", "for", "detail",
          "image", "photo", "picture", "view", "hanging", "wall", "historical", "vintage"}


def _keywords(query: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", query.lower()) if w not in _STOP}


def _relevant(title: str, query: str) -> bool:
    """Commons search also matches descriptions, which drags in unrelated
    files; require at least one meaningful query word in the file title."""
    kws = _keywords(query)
    t = title.lower()
    return not kws or any(k in t or k.rstrip("s") in t for k in kws)


_NOT_PHOTO = re.compile(r"\b(map|locator|location|results?|chart|diagram|flag|logo|seal|statue|fountain|stamp|"
                        r"coin|illustration|drawing|painting|skeleton|monument|sculpture|memorial|roundabout|"
                        r"museum|museo|museu|naturalis|naturkunde|specimens?|skull|skin|taxidermy|stuffed|toy|"
                        r"mascot|road[ _-]?kill(ed)?|killed|dead|carcass|keulemans|schlegel|lithograph|plate|brehm|"
                        r"lydekker|wolf, joseph)\b|keulemans|schlegel|\.svg$", re.I)

# "Genus species …" at the start of a query (wildlife beats ask for the scientific name)
_BINOMIAL = re.compile(r"^([A-Z][a-z]{3,})\s+([a-z]{3,})\b")


def _species_ok(page: dict, query: str) -> bool:
    """For a scientific-name query the file must really be that species: genus AND epithet in the
    title or in a Commons category. A loose word match ("night", "fruit") otherwise lets a fishing
    cat stand in for a leopard cat."""
    m = _BINOMIAL.match(query)
    if not m:
        return True
    genus, epithet = m.group(1).lower(), m.group(2).lower()
    hay = " ".join([page.get("title", "")] + [c.get("title", "") for c in page.get("categories", [])]).lower()
    return genus in hay and epithet in hay


def _commons_search(query: str, used: set[int], lock: threading.Lock,
                    photo: bool = False) -> list[tuple[int, str, str]]:
    """Usable Commons files for query, best first: (pageid, thumb url, credit)."""
    params = {
        "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
        "gsrsearch": query, "gsrlimit": 12, "prop": "imageinfo|categories", "cllimit": "max",
        "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 1600,
        "iiextmetadatafilter": "LicenseShortName|Artist",
    }
    r = requests.get(COMMONS_API, params=params, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    kws = _keywords(query)

    def score(p):  # the right species first, then most query words in the title, then Commons' ranking
        t = p.get("title", "").lower()
        return (not _species_ok(p, query), -sum(1 for k in kws if k in t or k.rstrip("s") in t),
                p.get("index", 99))

    pages = sorted((r.json().get("query", {}).get("pages", {}) or {}).values(), key=score)
    out = []
    for p in pages:
        if not _species_ok(p, query):
            continue
        if not _BINOMIAL.match(query) and not _relevant(p.get("title", ""), query):
            continue  # (a species query is already checked against title + categories)
        if photo and _NOT_PHOTO.search(p.get("title", "")):
            continue  # a "photo" beat must show a real photograph, not a map or results chart
        info = (p.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        lic = meta.get("LicenseShortName", {}).get("value", "")
        if not _OK_LICENSE.search(lic):
            continue
        if info.get("mime", "") not in ("image/jpeg", "image/png", "image/svg+xml", "image/tiff"):
            continue
        if min(info.get("width", 0), info.get("height", 0)) < 500 or not info.get("thumburl"):
            continue
        with lock:
            if p["pageid"] in used:
                continue
        artist = _strip_html(meta.get("Artist", {}).get("value", ""))[:60] or "Unknown"
        out.append((p["pageid"], info["thumburl"], f"ภาพ: {artist} · {lic} · Wikimedia Commons"))
    return out


_VERDICT = {"type": "object", "additionalProperties": False, "required": ["ok", "what"],
            "properties": {"ok": {"type": "boolean"}, "what": {"type": "string"}}}
MAX_CHECKS = 5          # vision checks per scene before giving up and using a card


def _verify(data: bytes, query: str, visual: str, about: str) -> tuple[bool, str]:
    """A quick look by a small vision model: is this really the picture the beat asked for?
    Without Claude configured there is no check (the filename filters above still apply)."""
    from PIL import Image

    from ..llm import claude_available, look

    if not claude_available():
        return True, "unchecked"
    try:
        im = Image.open(io.BytesIO(data)).convert("RGB")
    except OSError:
        return False, "unreadable"
    im.thumbnail((768, 768))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=85)
    m = _BINOMIAL.match(query)
    if m:
        rules = (f"It must be a real PHOTOGRAPH (not a drawing, painting, old plate, illustration, render, "
                 f"diagram or map) of a LIVE {m.group(1)} {m.group(2)} — exactly that species, clearly "
                 f"visible and recognisable. Reject: dead, roadkill, carcass, hunted, stuffed or taxidermy, "
                 f"museum specimen, skin, skull or bones, a different species, a cage or zoo sign as the "
                 f"main subject, gore, or an image where the animal is too tiny or blurry to identify.")
    elif visual == "map":
        rules = "It must be a clear map that matches the request."
    else:
        rules = ("It must clearly show what the request names (an archival photo, portrait or document is "
                 "fine). Reject unrelated subjects, gore, or images dominated by text/watermarks.")
    verdict = look(buf.getvalue(),
                   f"This image may be used in a short educational video. Beat topic: {about!r}. "
                   f"Requested image: {query!r}.\n{rules}\nSet ok=true only if it passes every rule. "
                   f"'what' = a few words on what the image actually shows.", _VERDICT)
    if verdict is None:
        return False, "check failed"
    return bool(verdict.get("ok")), str(verdict.get("what", ""))[:80]


def _wikimedia(query: str, visual: str, out: Path, used: set[int], lock, about: str = "") -> SceneImage | None:
    if not query:
        return None
    attempts = [query]
    if visual == "map" and "map" not in query.lower():
        attempts.insert(0, f"{query} map")
    words = query.split()
    if len(words) > 2:
        attempts.append(" ".join(words[:2]))
    checks = 0
    for q in attempts:
        try:
            hits = _commons_search(q, used, lock, photo=visual == "photo")
        except requests.RequestException as e:
            print(f"    [img] commons search failed ({e.__class__.__name__}); skipping")
            return None
        for pageid, url, credit in hits:
            if checks >= MAX_CHECKS:
                return None
            with lock:
                if pageid in used:
                    continue
                used.add(pageid)            # claimed: never offered to another beat, pass or fail
            try:
                img = requests.get(url, headers={"User-Agent": UA}, timeout=60)
            except requests.RequestException:
                continue
            if not (img.ok and img.content):
                continue
            checks += 1
            ok, what = _verify(img.content, q, visual, about)
            print(f"    [img] {'✓' if ok else '✗'} {url.rsplit('/', 1)[-1][:60]} — {what}")
            if ok:
                out.write_bytes(img.content)
                return SceneImage(out, credit, "wikimedia")
    return None


def _gateway(prompt: str, out: Path, budget: _Budget) -> SceneImage | None:
    key = ENV.get("AI_GATEWAY_API_KEY")
    if not (key and prompt) or not budget.take():
        return None
    try:
        r = requests.post(
            f"{ENV.get('LLM_BASE_URL', 'https://ai-gateway.vercel.sh/v1')}/chat/completions",
            headers={"Authorization": f"Bearer {key}"}, timeout=180,
            json={"model": STORY_IMAGE_MODEL, "modalities": ["text", "image"],
                  "messages": [{"role": "user", "content": prompt + ". Vertical 9:16. No text."}]},
        )
        if r.status_code in (401, 402, 403):
            budget.disabled = True
            print(f"    [img] AI images unavailable ({r.status_code}); using real images for this run")
            return None
        r.raise_for_status()
        images = r.json()["choices"][0]["message"].get("images") or []
        url = images[0]["image_url"]["url"] if images else ""
        if not url.startswith("data:"):
            return None
        out.write_bytes(base64.b64decode(url.split(",", 1)[1]))
        return SceneImage(out, "ภาพประกอบสร้างด้วย AI", "gateway")
    except (requests.RequestException, KeyError, IndexError, ValueError) as e:
        print(f"    [img] AI image failed: {e.__class__.__name__}")
        return None


def _chain(visual: str) -> list[str]:
    if STORY_IMAGE_PROVIDER == "cards":
        return []
    if STORY_IMAGE_PROVIDER == "wikimedia":
        return ["wikimedia"]
    if STORY_IMAGE_PROVIDER == "gateway":
        return ["gateway"]
    return ["gateway", "wikimedia"] if visual == "scene" else ["wikimedia", "gateway"]


def fetch_all(scenes, run_dir: Path) -> list[SceneImage]:
    """Resolve one image per scene (in parallel), falling back to cards."""
    from concurrent.futures import ThreadPoolExecutor

    run_dir.mkdir(parents=True, exist_ok=True)
    budget = _Budget(STORY_MAX_AI_IMAGES)
    used: set[int] = set()
    lock = threading.Lock()

    def resolve(i_scene) -> SceneImage:
        i, sc = i_scene
        for provider in _chain(sc.visual):
            if provider == "wikimedia":
                got = _wikimedia(sc.image_query, sc.visual, run_dir / f"img_{i}.jpg", used, lock,
                                about=getattr(sc, "narration", "") or getattr(sc, "card_title", ""))
            else:
                got = _gateway(sc.image_prompt, run_dir / f"img_{i}.png", budget)
            if got:
                print(f"    [img] scene {i}: {got.provider}")
                return got
        print(f"    [img] scene {i}: card")
        return SceneImage(globe_card(run_dir / f"card_{i}.jpg", highlight=sc.highlight, seed=i))

    with ThreadPoolExecutor(max_workers=4) as ex:
        results = list(ex.map(resolve, enumerate(scenes)))
    return results


def ai_images_used(results: list[SceneImage]) -> int:
    return sum(1 for r in results if r.provider == "gateway")
