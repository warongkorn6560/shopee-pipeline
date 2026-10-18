"""
Story writer: topic → narrated, scene-by-scene plan for a 40-55s vertical video.

Each scene carries its own narration segment, so the voiceover's character
timestamps can switch visuals exactly when the narrator moves on.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import requests

from ..config import STORY_LLM_MODEL, STORY_NICHE, STORY_SERIES_NAME
from ..scriptwriter import GATEWAY_MODEL, _llm_json

WIKI_UA = "ShopeePipelineStoryBot/1.0 (https://github.com/warongkorn6560/shopee-pipeline)"

RESEARCH_SYSTEM = "You find the Wikipedia articles a fact-checker needs. Raw JSON only."
RESEARCH_PROMPT = """Topic (Thai): {topic}
Angle: {angle}

List 1-3 Wikipedia articles that contain the facts needed to tell this story accurately.
Prefer English Wikipedia; add a Thai article ("th") when the topic is about Thailand.
Return: {{"articles": [{{"lang": "en", "title": "Mercator projection"}}]}}"""

TOPIC_SYSTEM = """You plan a Thai short-video edutainment series. You pick topics that make \
people stop scrolling: a surprising "why" or "how" with a clear, true answer. Raw JSON only."""

TOPIC_PROMPT = """Series: {series}
Niche: {niche}

Already covered (do not repeat or closely paraphrase):
{previous}

Propose ONE new topic. Rules:
- A curiosity question in Thai, at most 70 characters
- Answerable with well-documented facts (history, geography, maps, science of places)
- Neutral: no current politics, territorial disputes, religion debates, or living people
Return: {{"topic": "Thai question", "angle": "one Thai sentence on the storytelling angle"}}"""

STORY_SYSTEM = f"""You are the head writer of "{STORY_SERIES_NAME}", a Thai Facebook/TikTok \
edutainment page that tells true stories about places, maps and history in under a minute. \
Your narration sounds like a friendly documentary host: vivid, concrete, easy to follow, \
with one surprising fact that makes people share. You never invent facts. Raw JSON only."""

STORY_PROMPT = """Write a vertical-video story.

TOPIC: {topic}
ANGLE: {angle}

SOURCE NOTES (from Wikipedia — every fact you state must be supported here;
if the notes do not support a claim, leave it out)
{notes}

STRUCTURE (7-9 scenes, in order)
  1  HOOK     — one curiosity question or startling fact, max 70 Thai characters
  2-3 CONTEXT — where and when; ground the viewer on the map
  4-7 STORY   — the turning points: concrete names, places, years
  8  PAYOFF   — the answer / the surprising fact, said plainly
  9  OUTRO    — "กดติดตามไว้ แล้วมาฟังเรื่องเล่าตอนต่อไปกัน" + a short question for comments

NARRATION RULES
- Thai, spoken documentary style, total 320-450 Thai characters across all scenes (~40-50 seconds)
- Each scene's narration is ONE short sentence, max 80 Thai characters
- Do NOT use polite particles ครับ / ค่ะ / นะครับ / นะคะ — narrate like a documentary
- Only well-established facts. If a number or date is uncertain, describe it without the number
- Neutral and respectful: no current politics, no territorial claims, no stereotypes

ON-SCREEN CAPTION RULES
- Thai key phrase per scene, max 7 words, put spaces between phrases, no emoji

VISUAL RULES (one per scene)
- "visual": "map" | "photo" | "portrait" | "artifact" | "scene"
- "image_query": 2-5 ENGLISH keywords that would find a real image on Wikimedia Commons
  (e.g. "Mercator projection world map", "Ayutthaya historical park", "old map of Siam")
- "image_prompt": ENGLISH prompt for an illustration of the moment, painterly documentary
  style, vertical 9:16, absolutely no text or letters in the image
- "highlight": optional big stat shown on a title card (a year, distance, or 1-3 words), else ""
- The OUTRO scene uses visual "map" with a query for an antique map related to the topic

Return EXACTLY this JSON:
{{
  "title": "Thai on-screen title, max 38 characters",
  "scenes": [
    {{"narration": "...", "caption": "...", "visual": "map", "image_query": "...",
      "image_prompt": "...", "highlight": ""}}
  ],
  "post_caption": "Facebook post text in Thai: 2-4 short lines that tease the story, then a question for comments",
  "hashtags": ["5 hashtags starting with #, Thai and English"],
  "sources": ["2-4 short source names, e.g. Wikipedia: Mercator projection"]
}}"""


@dataclass
class StoryScene:
    narration: str
    caption: str
    visual: str = "photo"
    image_query: str = ""
    image_prompt: str = ""
    highlight: str = ""


@dataclass
class StoryPlan:
    topic: str
    title: str
    scenes: list[StoryScene]
    post_caption: str
    hashtags: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)

    @property
    def narration(self) -> str:
        return " ".join(s.narration for s in self.scenes)


def _ask(system: str, prompt: str, max_tokens: int) -> dict:
    """Story model first; fall back to the free default if it is refused."""
    try:
        return _llm_json(system, prompt, model=STORY_LLM_MODEL, max_tokens=max_tokens)
    except Exception as e:  # noqa: BLE001
        if STORY_LLM_MODEL == GATEWAY_MODEL or not any(c in str(e) for c in ("403", "404", "401")):
            raise
        print(f"  [writer] {STORY_LLM_MODEL} refused ({str(e)[:60]}…); using {GATEWAY_MODEL}")
        return _llm_json(system, prompt, model=GATEWAY_MODEL, max_tokens=max_tokens)


def _wiki_extract(lang: str, title: str, limit: int = 3500) -> tuple[str, str] | None:
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
        wanted = _ask(RESEARCH_SYSTEM, RESEARCH_PROMPT.format(topic=topic, angle=angle or "-"),
                      max_tokens=300).get("articles", [])[:3]
    except Exception as e:  # noqa: BLE001 — research is best-effort
        print(f"  [writer] research step failed: {e}")
        return []
    notes = []
    for a in wanted:
        lang = "th" if str(a.get("lang", "en")).lower().startswith("th") else "en"
        got = _wiki_extract(lang, str(a.get("title", "")).strip())
        if got:
            notes.append((f"Wikipedia{' (ไทย)' if lang == 'th' else ''}: {got[0]}", got[1]))
    print(f"  [writer] sources: {[n[0] for n in notes] or 'none found'}")
    return notes


def propose_topic(previous: list[str]) -> tuple[str, str]:
    data = _ask(TOPIC_SYSTEM, TOPIC_PROMPT.format(
        series=STORY_SERIES_NAME, niche=STORY_NICHE,
        previous="\n".join(f"- {p}" for p in previous[-60:]) or "- (none yet)"),
        max_tokens=400)
    return data["topic"].strip(), data.get("angle", "").strip()


def write_story(topic: str, angle: str = "") -> StoryPlan:
    notes = research(topic, angle)
    notes_text = "\n\n".join(f"[{label}]\n{text}" for label, text in notes) or \
        "(no notes found — use only facts that are common textbook knowledge)"
    data = _ask(STORY_SYSTEM, STORY_PROMPT.format(topic=topic, angle=angle or "-", notes=notes_text),
                max_tokens=3500)
    scenes = [
        StoryScene(
            narration=str(s.get("narration", "")).strip(),
            caption=str(s.get("caption", "")).strip(),
            visual=str(s.get("visual", "photo")).strip().lower(),
            image_query=str(s.get("image_query", "")).strip(),
            image_prompt=str(s.get("image_prompt", "")).strip(),
            highlight=str(s.get("highlight", "")).strip(),
        )
        for s in data.get("scenes", []) if str(s.get("narration", "")).strip()
    ][:10]
    if len(scenes) < 4:
        raise RuntimeError(f"Story plan too short ({len(scenes)} scenes).")
    # Keep the voiceover under ~60s even if the model over-writes: drop middle
    # story beats, never the hook (first) or the payoff + outro (last two).
    while sum(len(s.narration) for s in scenes) > 520 and len(scenes) > 5:
        scenes.pop(len(scenes) // 2)
    return StoryPlan(
        topic=topic, title=str(data.get("title", topic)).strip()[:60], scenes=scenes,
        post_caption=str(data.get("post_caption", "")).strip(),
        hashtags=[h for h in data.get("hashtags", []) if str(h).startswith("#")][:6],
        sources=[label for label, _ in notes] or [str(s) for s in data.get("sources", [])][:4],
    )


def mock_story(topic: str) -> StoryPlan:
    """Offline plan (no API) for testing the renderer."""
    scenes = [
        StoryScene("รู้ไหม ในแผนที่โลกที่เราเห็นกันทุกวัน เกาะกรีนแลนด์ดูใหญ่พอๆ กับทวีปแอฟริกา",
                   "กรีนแลนด์ ใหญ่เท่าแอฟริกา จริงไหม", "map", "Mercator projection world map", "", ""),
        StoryScene("แต่ความจริงแล้ว แอฟริกาใหญ่กว่ากรีนแลนด์ถึงประมาณสิบสี่เท่า",
                   "แอฟริกาใหญ่กว่า ราว 14 เท่า", "map", "Greenland Africa size comparison", "", "14 เท่า"),
        StoryScene("ต้นเหตุคือแผนที่แบบเมอร์เคเตอร์ ที่วาดขึ้นในปี ค.ศ. 1569 เพื่อช่วยนักเดินเรือ",
                   "แผนที่เมอร์เคเตอร์ ค.ศ. 1569", "portrait", "Gerardus Mercator portrait", "", "ค.ศ. 1569"),
        StoryScene("การคลี่ลูกโลกให้แบน ทำให้ดินแดนใกล้ขั้วโลกถูกยืดจนดูใหญ่เกินจริง",
                   "ยิ่งใกล้ขั้วโลก ยิ่งถูกยืด", "map", "Tissot indicatrix Mercator", "", ""),
        StoryScene("แผนที่นี้ยังเหมาะกับการเดินเรือ เพราะรักษามุมและทิศทางได้ถูกต้อง",
                   "รักษาทิศทาง เพื่อการเดินเรือ", "artifact", "antique nautical chart compass", "", ""),
        StoryScene("กดติดตามไว้ แล้วมาฟังเรื่องเล่าตอนต่อไปกัน คุณเคยเข้าใจผิดเรื่องนี้ไหม",
                   "กดติดตาม ฟังตอนต่อไป", "map", "antique world map", "", ""),
    ]
    return StoryPlan(topic=topic, title="กรีนแลนด์ ใหญ่จริงหรือแค่ภาพลวงตา", scenes=scenes,
                     post_caption="แผนที่ที่เราเห็นมาตั้งแต่เด็ก อาจหลอกตาเรามาตลอด\nคุณเคยคิดว่ากรีนแลนด์ใหญ่แค่ไหน?",
                     hashtags=["#เรื่องเล่าจากแผนที่", "#แผนที่โลก", "#ความรู้รอบตัว", "#Geography", "#Maps"],
                     sources=["Wikipedia: Mercator projection", "Wikipedia: Greenland"])
