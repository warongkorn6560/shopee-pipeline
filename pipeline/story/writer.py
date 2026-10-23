"""
Story writer / showrunner for Flow B.

topic → Wikipedia research → one structured plan: narration per beat (display
text + a TTS-ready spoken version), a title card per beat, and a shot for each
beat (which real map features to draw, which places to label, how far the
camera zooms) that the renderer executes literally.

Claude (ANTHROPIC_API_KEY) writes it with a schema-constrained JSON response;
without a key the AI Gateway fallback receives the same schema in the prompt.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import requests

from ..config import STORY_NICHE, STORY_SERIES_NAME, STORY_TARGET_SECONDS
from ..llm import generate_json

WIKI_UA = "ShopeePipelineStoryBot/1.0 (https://github.com/warongkorn6560/shopee-pipeline)"
CHARS_PER_SECOND = 13  # measured: Thai narrator "Duang" on eleven_v4 speaks ~14 chars/s


def _obj(props: dict) -> dict:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


_S, _N = {"type": "string"}, {"type": "number"}

FOCUS_SCHEMA = _obj({
    "name": _S,
    "kind": {"type": "string", "enum": ["waterway", "road", "railway", "admin_area", "area", "place"]},
    "style": {"type": "string", "enum": ["line", "area", "pin"]},
    "number": _S,
})
BEAT_SCHEMA = _obj({
    "narration": _S, "spoken": _S,
    "card_title": _S, "card_subtitle": _S, "card_fact": _S,
    "shot": {"type": "string", "enum": ["map", "photo"]},
    "focus": {"type": "array", "items": FOCUS_SCHEMA},
    "labels": {"type": "array", "items": _S},
    "span_start_km": _N, "span_end_km": _N,
    "photo_query": _S,
})
STORY_SCHEMA = _obj({
    "title": _S, "hook_title": _S, "hook_subtitle": _S,
    "region": _obj({"name": _S, "west": _N, "south": _N, "east": _N, "north": _N}),
    "beats": {"type": "array", "items": BEAT_SCHEMA},
    "post_caption": _S, "comment_question": _S,
    "hashtags": {"type": "array", "items": _S},
})
TOPIC_SCHEMA = _obj({"topic": _S, "angle": _S})
RESEARCH_SCHEMA = _obj({"articles": {"type": "array", "items": _obj({"lang": {"type": "string", "enum": ["th", "en"]}, "title": _S})}})


SHOWRUNNER = f"""You are the showrunner of "{STORY_SERIES_NAME}", a Thai Facebook/TikTok page that explains \
places through animated satellite maps: real satellite imagery, glowing lines tracing canals, rivers, \
roads or rail, highlighted districts, numbered pins, geo-anchored Thai labels, and a bold title card \
on every beat. A Thai narrator reads your script.

What makes this format get 100K+ views (learned from the leading Thai map page):
- Hyper-local curiosity that Thai viewers feel personally: "คลองเลข 1-33 อยู่ตรงไหน?",
  "บ้านคุณอยู่คลองไหน?" — a question people answer in the comments.
- A list or journey the camera can walk through beat by beat (canal 1 → 13 → 33, station by
  station, district by district), each beat with its own card and one concrete number.
- Dense, specific facts: years (พ.ศ.), lengths (กม.), counts, names of districts and kings.
- Plain spoken Thai like a friendly documentary host. Short sentences. No filler, no vague
  generalities ("เทคโนโลยีช่วยให้…" is banned), no moralising.
- Only facts supported by the SOURCE NOTES. If unsure of a number, leave the number out.
- Neutral: no politics, no territorial disputes, no claims about living people."""

STORY_PROMPT = """TOPIC: {topic}
ANGLE: {angle}

SOURCE NOTES (Wikipedia):
{notes}

Write the plan for one vertical video of about {seconds} seconds.

BEATS — 9 to 14, in order:
  1. HOOK: wide map of the region, card = the curiosity question. Narration ≤ 2 short sentences.
  2-3. CONTEXT: where/when, zoom toward the subject.
  middle beats: the list/journey — one item per beat, each with its own card and fact.
  second-to-last: the payoff / surprising fact.
  last: CTA — ask the comment question, then "กดติดตาม{series} ไว้ แล้วมาดูตอนต่อไปกัน".

FIELDS PER BEAT
- narration: what viewers read in subtitles (Thai, numbers as digits OK). Put a space between
  phrases every 8-25 characters, the way Thai is normally spaced, so subtitles break cleanly.
- spoken: the SAME sentence written for text-to-speech: every number, year and unit spelled out in
  Thai words (พ.ศ. 2433 → พุทธศักราชสองพันสี่ร้อยสามสิบสาม, 25 กม. → ยี่สิบห้ากิโลเมตร,
  ร.5 → รัชกาลที่ห้า), no symbols, no English abbreviations, no emoji.
  All spoken text together: {chars_min}-{chars_max} Thai characters.
- card_title: big title on the card, max 14 characters (e.g. "คลอง 6", "ทุ่งรังสิต").
- card_subtitle: max 34 characters (places, names — e.g. "คลองหลวง · วังน้อย · ลำลูกกา").
- card_fact: max 34 characters, one number fact (e.g. "ปทุมธานี / อยุธยา · ยาว ~39 กม."), or "".
- shot: "map" for almost every beat. "photo" only when a real historical photo or portrait OF THIS
  EXACT THAI PLACE OR PERSON is essential (max 2 per video) — then set photo_query to 2-5 ENGLISH
  Wikimedia Commons keywords that name it (e.g. "Saen Saep canal Bangkok 1900"). If unsure such a
  photo exists, use "map".
- focus: map features to draw. Use names exactly as they appear in OpenStreetMap Thailand (Thai):
  e.g. {{"name": "คลองรังสิตประยูรศักดิ์", "kind": "waterway", "style": "line", "number": ""}},
  {{"name": "อำเภอธัญบุรี", "kind": "admin_area", "style": "area", "number": ""}},
  {{"name": "ตลาดรังสิต", "kind": "place", "style": "pin", "number": "1"}}.
  kind: waterway | road | railway | admin_area | area | place. style: line | area | pin.
  "number" is the label on a pin ("6", "13") or "". 0-3 features per beat; the beat's subject first.
- labels: 2-6 Thai place names to label on the map for orientation (provinces, districts, towns).
- span_start_km / span_end_km: map width in km at the start and end of the beat (the camera
  zooms between them). Hook ~ 80-250, district beats ~ 10-40. Keep the ratio ≤ 4.

REGION: lon/lat box (west, south, east, north) that contains every place in the story.

ALSO
- title: video title, max 40 characters.
- hook_title (max 14) + hook_subtitle (max 32): the opening card.
- post_caption: 1-2 short curiosity lines for the Facebook post, then the comment question and
  "คอมเมนต์บอกกันหน่อย 👇". No hashtags here.
- comment_question: the question viewers answer.
- hashtags: 5 hashtags starting with #, including #{series_tag}."""

TOPIC_PROMPT = """Series: {series}
Niche: {niche}

Already covered (do not repeat or closely paraphrase):
{previous}

Propose ONE new topic for this Thai map-storytelling page. It must be:
- About a place IN THAILAND that Thai viewers know personally: a canal, river, road, rail line,
  district, old town name, market, island, megaproject, or how an area got its shape or name.
- Answerable with well-documented facts and drawable on a satellite map (things with a location).
- A curiosity question Thai people want to comment on ("…อยู่ตรงไหน?", "ทำไม…ถึงชื่อนี้?", "…มีกี่…?").
- NOT foreign, NOT abstract, NOT politics or territorial disputes.
Write topic (Thai question, ≤ 70 characters) and angle (one Thai sentence: the list or journey the
camera will walk through)."""


@dataclass
class StoryScene:
    narration: str
    caption: str = ""
    visual: str = "map"
    image_query: str = ""
    image_prompt: str = ""
    highlight: str = ""
    spoken: str = ""
    card_title: str = ""
    card_subtitle: str = ""
    card_fact: str = ""
    focus: list[dict] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    span_start_km: float = 60.0
    span_end_km: float = 30.0


@dataclass
class StoryPlan:
    topic: str
    title: str
    scenes: list[StoryScene]
    post_caption: str
    hashtags: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    hook_title: str = ""
    hook_subtitle: str = ""
    region: dict = field(default_factory=dict)
    comment_question: str = ""

    @property
    def narration(self) -> str:
        return " ".join(s.narration for s in self.scenes)

    @property
    def spoken(self) -> str:
        return " ".join(s.spoken or s.narration for s in self.scenes)


# ---------------------------------------------------------------------------
# Research
# ---------------------------------------------------------------------------
def _wiki_extract(lang: str, title: str, limit: int = 5000) -> tuple[str, str] | None:
    api = f"https://{lang}.wikipedia.org/w/api.php"
    h = {"User-Agent": WIKI_UA}
    try:
        s = requests.get(api, headers=h, timeout=20, params={
            "action": "query", "list": "search", "srsearch": title, "srlimit": 1, "format": "json"})
        hits = s.json().get("query", {}).get("search", [])
        if not hits:
            return None
        resolved = hits[0]["title"]
        e = requests.get(api, headers=h, timeout=20, params={
            "action": "query", "prop": "extracts", "explaintext": 1, "redirects": 1,
            "titles": resolved, "format": "json", "formatversion": 2})
        text = (e.json().get("query", {}).get("pages", [{}])[0].get("extract") or "").strip()
        return (resolved, text[:limit]) if text else None
    except (requests.RequestException, ValueError, KeyError, IndexError):
        return None


def research(topic: str, angle: str) -> list[tuple[str, str]]:
    """Wikipedia excerpts the writer must stay within: [(label, text)]."""
    try:
        wanted = generate_json(
            "You find the Wikipedia articles a fact-checker needs.",
            f"Topic (Thai): {topic}\nAngle: {angle}\n\nList 2-4 Wikipedia articles with the facts needed "
            "to tell this story accurately. Prefer Thai Wikipedia for Thai places, add English when it is "
            "more detailed.",
            schema=RESEARCH_SCHEMA, max_tokens=2000, effort="low",
        ).get("articles", [])[:4]
    except Exception as e:  # noqa: BLE001 — research is best-effort
        print(f"  [writer] research step failed: {e}")
        return []
    notes = []
    for a in wanted:
        lang = "th" if str(a.get("lang", "th")).startswith("th") else "en"
        got = _wiki_extract(lang, str(a.get("title", "")).strip())
        if got:
            notes.append((f"Wikipedia{' (ไทย)' if lang == 'th' else ''}: {got[0]}", got[1]))
    print(f"  [writer] sources: {[n[0] for n in notes] or 'none found'}")
    return notes


def propose_topic(previous: list[str]) -> tuple[str, str]:
    data = generate_json(
        "You plan topics for a Thai map-storytelling page. Every topic is a real place in Thailand.",
        TOPIC_PROMPT.format(series=STORY_SERIES_NAME, niche=STORY_NICHE,
                            previous="\n".join(f"- {p}" for p in previous[-80:]) or "- (none yet)"),
        schema=TOPIC_SCHEMA, max_tokens=2000, effort="low", gateway_model="openai/gpt-4.1-mini",
    )
    return data["topic"].strip(), data.get("angle", "").strip()


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------
def _clamp(v, lo, hi, default):
    try:
        return max(lo, min(hi, float(v)))
    except (TypeError, ValueError):
        return default


def _scene(b: dict) -> StoryScene:
    shot = b.get("shot", "map")
    start = _clamp(b.get("span_start_km"), 2, 900, 60)
    end = _clamp(b.get("span_end_km"), 2, 900, start * 0.6)
    if max(start, end) / min(start, end) > 4:  # keep the zoom within one mosaic level
        end = start / 4 if end < start else start * 4
    focus = [f for f in (b.get("focus") or []) if str(f.get("name", "")).strip()][:3]
    return StoryScene(
        narration=str(b.get("narration", "")).strip(),
        spoken=str(b.get("spoken", "")).strip() or str(b.get("narration", "")).strip(),
        caption=str(b.get("card_title", "")).strip(),
        visual="photo" if shot == "photo" else "map",
        image_query=str(b.get("photo_query", "")).strip(),
        card_title=str(b.get("card_title", "")).strip()[:20],
        card_subtitle=str(b.get("card_subtitle", "")).strip()[:44],
        card_fact=str(b.get("card_fact", "")).strip()[:44],
        highlight=str(b.get("card_fact", "")).strip()[:20],
        focus=focus,
        labels=[str(x).strip() for x in (b.get("labels") or []) if str(x).strip()][:6],
        span_start_km=start, span_end_km=end,
    )


def write_story(topic: str, angle: str = "") -> StoryPlan:
    notes = research(topic, angle)
    notes_text = "\n\n".join(f"[{label}]\n{text}" for label, text in notes) or \
        "(no notes found — use only facts that are common textbook knowledge)"
    seconds = STORY_TARGET_SECONDS
    series_tag = STORY_SERIES_NAME.replace(" ", "")
    data = generate_json(
        SHOWRUNNER,
        STORY_PROMPT.format(topic=topic, angle=angle or "-", notes=notes_text, seconds=seconds,
                            chars_min=int(seconds * CHARS_PER_SECOND * 0.85),
                            chars_max=int(seconds * CHARS_PER_SECOND * 1.1),
                            series=STORY_SERIES_NAME, series_tag=series_tag),
        schema=STORY_SCHEMA, max_tokens=32000, gateway_model="openai/gpt-4.1-mini",
    )
    scenes = [_scene(b) for b in data.get("beats", []) if str(b.get("narration", "")).strip()][:16]
    if len(scenes) < 5:
        raise RuntimeError(f"Story plan too short ({len(scenes)} beats).")
    region = data.get("region") or {}
    return StoryPlan(
        topic=topic, title=str(data.get("title", topic)).strip()[:60], scenes=scenes,
        post_caption=str(data.get("post_caption", "")).strip(),
        hashtags=[h for h in data.get("hashtags", []) if str(h).startswith("#")][:6],
        sources=[label for label, _ in notes],
        hook_title=str(data.get("hook_title", "")).strip()[:20],
        hook_subtitle=str(data.get("hook_subtitle", "")).strip()[:40],
        region={k: region.get(k) for k in ("name", "west", "south", "east", "north")},
        comment_question=str(data.get("comment_question", "")).strip(),
    )


def mock_story(topic: str) -> StoryPlan:
    """Offline plan (no LLM) with real geography, for testing the map renderer."""
    def b(n, sp, title, sub, fact, focus, labels, s0, s1):
        return StoryScene(narration=n, spoken=sp, card_title=title, card_subtitle=sub, card_fact=fact,
                          caption=title, highlight=fact, focus=focus, labels=labels,
                          span_start_km=s0, span_end_km=s1)
    canal = {"name": "คลองรังสิตประยูรศักดิ์", "kind": "waterway", "style": "line", "number": ""}
    scenes = [
        b("คลองหนึ่ง คลองสอง เรียกกันจนชิน แต่รู้ไหมว่าคลองเลขไปสุดที่เลขอะไร?",
          "คลองหนึ่ง คลองสอง เรียกกันจนชิน แต่รู้ไหมว่าคลองเลขไปสุดที่เลขอะไร",
          "ทุ่งรังสิต", "คลองเลข 1-33 อยู่ตรงไหน?", "", [canal],
          ["ปทุมธานี", "กรุงเทพมหานคร", "นครนายก", "พระนครศรีอยุธยา"], 140, 90),
        b("ทุกอย่างเริ่มจากคลองรังสิตประยูรศักดิ์ ขุดในสมัยรัชกาลที่ 5 เมื่อ พ.ศ. 2433",
          "ทุกอย่างเริ่มจากคลองรังสิตประยูรศักดิ์ ขุดในสมัยรัชกาลที่ห้า เมื่อพุทธศักราชสองพันสี่ร้อยสามสิบสาม",
          "คลองรังสิตฯ", "ขุดสมัยรัชกาลที่ 5", "พ.ศ. 2433", [canal], ["ปทุมธานี", "ธัญบุรี"], 70, 35),
        b("คลองซอยถูกขุดตัดผ่านเป็นตาราง แล้วเรียกชื่อเป็นตัวเลขเรียงกันไป",
          "คลองซอยถูกขุดตัดผ่านเป็นตาราง แล้วเรียกชื่อเป็นตัวเลขเรียงกันไป",
          "คลองซอย", "ตั้งชื่อเป็นตัวเลข", "", [canal, {"name": "อำเภอธัญบุรี", "kind": "admin_area", "style": "area", "number": ""}],
          ["ธัญบุรี", "ลำลูกกา"], 45, 25),
        b("วันนี้ทุ่งนาเหล่านั้นกลายเป็นบ้าน ตลาด และมหาวิทยาลัยหลายแห่ง",
          "วันนี้ทุ่งนาเหล่านั้นกลายเป็นบ้าน ตลาด และมหาวิทยาลัยหลายแห่ง",
          "ทุ่งรังสิตวันนี้", "จากนาข้าวสู่เมือง", "", [{"name": "รังสิต", "kind": "place", "style": "pin", "number": "1"}],
          ["รังสิต", "คลองหลวง"], 30, 15),
        b("บ้านคุณอยู่คลองเลขอะไร คอมเมนต์บอกกันหน่อย กดติดตามไว้ แล้วมาดูตอนต่อไปกัน",
          "บ้านคุณอยู่คลองเลขอะไร คอมเมนต์บอกกันหน่อย กดติดตามไว้ แล้วมาดูตอนต่อไปกัน",
          "บ้านคุณคลองไหน?", "คอมเมนต์บอกกันหน่อย", "", [canal], ["ปทุมธานี"], 90, 120),
    ]
    return StoryPlan(topic=topic, title="ทุ่งรังสิต คลองเลขไปสุดที่เท่าไหร่", scenes=scenes,
                     post_caption="คลองหนึ่ง คลองสอง เรียกกันจนชิน แต่คลองเลขไปสุดที่เลขอะไร?\nบ้านคุณคลองไหน คอมเมนต์บอกกันหน่อย 👇",
                     hashtags=["#ทุ่งรังสิต", "#คลองรังสิต", "#ปทุมธานี", "#ชื่อบ้านนามเมือง", "#เรื่องเล่าจากแผนที่"],
                     sources=["Wikipedia (ไทย): คลองรังสิตประยูรศักดิ์"],
                     hook_title="ทุ่งรังสิต", hook_subtitle="คลองเลข 1-33 อยู่ตรงไหน?",
                     region={"name": "ทุ่งรังสิต", "west": 100.45, "south": 13.85, "east": 101.15, "north": 14.25},
                     comment_question="บ้านคุณอยู่คลองเลขอะไร?")
