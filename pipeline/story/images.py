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


_NOT_PHOTO = re.compile(r"\b(map|locator|location|results?|chart|diagram|flag|logo|seal)\b|\.svg$", re.I)


def _commons_search(query: str, used: set[int], lock: threading.Lock,
                    photo: bool = False) -> tuple[str, str] | None:
    params = {
        "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
        "gsrsearch": query, "gsrlimit": 12, "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 1600,
        "iiextmetadatafilter": "LicenseShortName|Artist",
    }
    r = requests.get(COMMONS_API, params=params, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    pages = sorted((r.json().get("query", {}).get("pages", {}) or {}).values(),
                   key=lambda p: p.get("index", 99))
    for p in pages:
        if not _relevant(p.get("title", ""), query):
            continue
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
            used.add(p["pageid"])
        artist = _strip_html(meta.get("Artist", {}).get("value", ""))[:60] or "Unknown"
        return info["thumburl"], f"ภาพ: {artist} · {lic} · Wikimedia Commons"
    return None


def _wikimedia(query: str, visual: str, out: Path, used: set[int], lock) -> SceneImage | None:
    if not query:
        return None
    attempts = [query]
    if visual == "map" and "map" not in query.lower():
        attempts.insert(0, f"{query} map")
    words = query.split()
    if len(words) > 2:
        attempts.append(" ".join(words[:2]))
    for q in attempts:
        try:
            hit = _commons_search(q, used, lock, photo=visual == "photo")
        except requests.RequestException as e:
            print(f"    [img] commons search failed ({e.__class__.__name__}); skipping")
            return None
        if hit:
            url, credit = hit
            img = requests.get(url, headers={"User-Agent": UA}, timeout=60)
            if img.ok and img.content:
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
                got = _wikimedia(sc.image_query, sc.visual, run_dir / f"img_{i}.jpg", used, lock)
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
