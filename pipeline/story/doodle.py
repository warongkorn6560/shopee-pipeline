"""
"doodle" style for the mystery theme: a first-person everyday story ("ผม…") — a neighbour, landlord,
co-worker or customer problem that escalates, then a clever, legal comeback or twist — told with hand-drawn
doodle characters over real, stylised photos of ordinary places (doodle_render.py). Fiction, labelled
"เรื่องสมมติ".
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from ..config import ASSETS, STORY_SERIES_NAME, STORY_TARGET_SECONDS
from ..llm import generate_json
from .doodle_cast import COLORS, EXPRESSIONS, HAIRS, POSES
from .writer import CHARS_PER_SECOND, StoryPlan, StoryScene, _obj

_S, _I = {"type": "string"}, {"type": "integer"}
BG_DIR = ASSETS / "doodle_bg"
FICTION = "เรื่องสมมติ ไม่เกี่ยวข้องกับบุคคลจริง"


def locations() -> list[str]:
    """Places we have a background photo for (assets/doodle_bg/<place>_<n>.jpg)."""
    names = sorted({p.stem.rsplit("_", 1)[0] for p in BG_DIR.glob("*.jpg")})
    return names or ["street"]


def _schema(places: list[str]) -> dict:
    who = _obj({"who": _I, "expression": {"type": "string", "enum": list(EXPRESSIONS)},
                "pose": {"type": "string", "enum": list(POSES)}})
    beat = _obj({
        "narration": _S, "spoken": _S,
        "shot": {"type": "string", "enum": ["scene", "guess", "twist"]},
        "place": {"type": "string", "enum": places},
        "on_screen": {"type": "array", "items": who},
        "tag": _S,
    })
    return _obj({
        "title": _S,
        "cast": {"type": "array", "items": _obj({
            "name": _S, "role": _S, "hair": {"type": "string", "enum": list(HAIRS)}, "glasses": {"type": "boolean"},
            "color": {"type": "string", "enum": list(COLORS)}})},
        "rain": {"type": "boolean"},
        "beats": {"type": "array", "items": beat},
        "explanation": _S,
        "post_caption": _S, "comment_question": _S,
        "hashtags": {"type": "array", "items": _S},
    })


SHOWRUNNER = f"""You write "{STORY_SERIES_NAME}", a Thai short-video series of first-person everyday stories told \
like a friend telling you what happened ("ผมเจอเพื่อนบ้าน…"). Each episode is a relatable conflict with a \
neighbour, landlord, co-worker, customer, relative or stranger that escalates ("เป็นครั้งที่ 4 แล้ว") and ends \
in a clever twist or comeback that makes viewers say "เฮ้ย ฉลาด" and tag a friend. It is drawn as simple doodle \
characters over real photos of ordinary places, and read by one casual male narrator.

Voice: spoken Thai the way people actually talk — short lines, "ผม", "เขา", "แล้วรู้ไหม…", "สรุปคือ…",
natural particles (ครับ, อะ, เลย) used sparingly. No formal narration, no literary words, no moralising,
no "สวัสดีครับ". Every line moves the story.

Rules:
- Fiction: invented people; no real names, celebrities, brands, companies, or identifiable places.
- The comeback/twist is LEGAL and NON-VIOLENT: no property damage, no threats, no harassment, no doxxing,
  no humiliating posts about someone, no unsafe or illegal tricks. Clever use of rules, timing, a
  misunderstanding revealed, or the other person's own trick backfiring are all great.
- Platform-safe: no blood, weapons, sexual content, self-harm, drugs; nobody mocked for gender, ethnicity,
  religion, disability, age or class.
- The twist must be consistent with what was shown earlier (plant it early, pay it off)."""

PROMPT = """PREMISE: {topic}
NOTES: {angle}

Write one vertical episode of about {seconds} seconds: 12 to 18 short beats (one or two spoken lines
each, 2-5 seconds).

STRUCTURE
- beat 1: the hook — the whole conflict in one line (it's also what makes people stop scrolling).
- then the setup and escalation (show it happening again and again; a tag like "ครั้งที่ 4" helps).
- plant the detail the twist will use, early and casually.
- optionally one "guess" beat right before the comeback: "ทายสิ ผมทำยังไง" style (shot = "guess").
- the comeback / twist (shot = "twist" on the beat it lands), the other person's reaction.
- last beat: a one-line punchline, then "กดติดตามไว้ เดี๋ยวมีเรื่องใหม่มาเล่า".

CAST: 2-4 people. cast[0] is always the narrator ("ผม", e.g. role "ผมเอง"); others get an everyday Thai
name or label ≤ 12 characters ("ป้าข้างห้อง", "พี่นิติ") and a role. hair/glasses/color make each one
recognisable — give everyone a different color.

FIELDS PER BEAT
- narration: the subtitle (one line ≤ 40 characters is best; split long sentences into more beats).
- spoken: the SAME words for text-to-speech, numbers and times in Thai words, no symbols or emoji.
  All spoken text together: {chars_min}-{chars_max} Thai characters.
- place: where this beat happens, one of: {places}. Keep the same place for a run of 2-4 beats, then
  move with the story (hallway → lobby → meeting room → parking…): use at least 4 different places.
- on_screen: 1-2 people visible: who (cast index), expression ({expressions}), pose ({poses}).
  Use the narrator in most beats; show who is talking or reacting.
- tag: a short on-screen label ≤ 14 characters ("ครั้งที่ 4", "ตีสอง", "3 วันต่อมา") or "".

ALSO
- title: the hook as an on-screen headline ≤ 46 characters (e.g. "เพื่อนบ้านแย่งที่จอดตรงผมไม่เลิก ผมเลย…").
- rain: true if the story happens in the rain (adds rain to outdoor shots).
- explanation: 1-2 Thai sentences on why the twist works (for the editor).
- post_caption: the hook in 1-2 lines (no spoiler), the comment question, then "คอมเมนต์มาคุยกัน 👇". No hashtags.
- comment_question: a question viewers love to answer ("ถ้าเป็นคุณจะทำยังไง?").
- hashtags: 5 hashtags starting with #, including #{series_tag}."""


@dataclass
class DoodlePlan(StoryPlan):
    cast: list[dict] = field(default_factory=list)
    rain: bool = False
    explanation: str = ""


def _int(v, lo, hi, default):
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return default


def _scene(b: dict, n_cast: int, places: list[str]) -> StoryScene:
    shot = b.get("shot") if b.get("shot") in ("scene", "guess", "twist") else "scene"
    sc = StoryScene(
        narration=str(b.get("narration", "")).strip(),
        spoken=str(b.get("spoken", "")).strip() or str(b.get("narration", "")).strip(),
        visual=shot, place=b.get("place") if b.get("place") in places else places[0],
        punch=str(b.get("tag", "")).strip()[:18],
    )
    people = []
    for w in (b.get("on_screen") or [])[:2]:
        k = _int(w.get("who"), 0, n_cast - 1, 0)
        if k not in [p[0] for p in people]:
            people.append((k, w.get("expression") if w.get("expression") in EXPRESSIONS else "neutral",
                           w.get("pose") if w.get("pose") in POSES else "stand"))
    sc.people = people or [(0, "neutral", "stand")]
    return sc


def write_doodle(topic: str, angle: str = "") -> DoodlePlan:
    places = locations()
    seconds = min(STORY_TARGET_SECONDS, 60)
    data = generate_json(
        SHOWRUNNER,
        PROMPT.format(topic=topic, angle=angle or "-", seconds=seconds,
                      chars_min=int(seconds * CHARS_PER_SECOND * 0.8), chars_max=int(seconds * CHARS_PER_SECOND),
                      places=", ".join(places), expressions=", ".join(EXPRESSIONS), poses=", ".join(POSES),
                      series_tag=STORY_SERIES_NAME.replace(" ", "")),
        schema=_schema(places), max_tokens=24000, gateway_model="openai/gpt-4.1-mini",
    )
    cast = [{"name": str(c.get("name", "")).strip()[:16], "role": str(c.get("role", "")).strip()[:20],
             "hair": c.get("hair") if c.get("hair") in HAIRS else "short", "glasses": bool(c.get("glasses")),
             "color": c.get("color") if c.get("color") in COLORS else "blue"}
            for c in data.get("cast") or []][:4] or [{"name": "ผม", "role": "ผมเอง", "hair": "short",
                                                     "glasses": True, "color": "blue"}]
    scenes = [_scene(b, len(cast), places) for b in data.get("beats", []) if str(b.get("narration", "")).strip()][:20]
    if len(scenes) < 8:
        raise RuntimeError(f"Doodle plan too short ({len(scenes)} beats).")
    title = str(data.get("title", topic)).strip()[:60]
    return DoodlePlan(
        topic=topic, title=title, scenes=scenes, post_caption=str(data.get("post_caption", "")).strip(),
        hashtags=[h for h in data.get("hashtags", []) if str(h).startswith("#")][:6], sources=[],
        hook_title=title, comment_question=str(data.get("comment_question", "")).strip(), style="doodle",
        cast=cast, rain=bool(data.get("rain")), explanation=str(data.get("explanation", "")).strip(),
    )


def credits(plan: DoodlePlan) -> list[str]:
    """Attribution lines for the background photos this episode used."""
    try:
        meta = json.loads((BG_DIR / "credits.json").read_text())
    except (OSError, ValueError):
        return []
    used = {getattr(s, "bg_file", "") for s in plan.scenes}
    return sorted({f"{m['title']} — {m['artist']} ({m['license']})" for f, m in meta.items() if f in used})


def mock_doodle(topic: str) -> DoodlePlan:
    def b(n, place, people, shot="scene", tag=""):
        return _scene({"narration": n, "spoken": n, "shot": shot, "place": place, "tag": tag,
                       "on_screen": [{"who": w, "expression": e, "pose": p} for w, e, p in people]}, 3, locations())
    p0 = "parking" if "parking" in locations() else locations()[0]
    scenes = [
        b("เพื่อนบ้านแย่งที่จอดรถตรงผมไม่เลิก", p0, [(0, "angry", "stand")]),
        b("ที่จอดนี้ผมเช่ามา มีป้ายชื่อห้องผมชัดๆ", p0, [(0, "neutral", "point")]),
        b("แต่พี่ห้องข้างๆ ก็จอดทับทุกคืน", p0, [(1, "smug", "stand"), (0, "sad", "stand")], tag="คืนแรก"),
        b("ผมแปะโน้ตขอดีๆ เขาก็ยิ้มรับ", p0, [(1, "happy", "stand"), (0, "neutral", "phone")]),
        b("คืนต่อมา จอดอีก", p0, [(1, "smug", "walk")], tag="ครั้งที่ 4"),
        b("ผมเลยไปคุยกับนิติ", p0, [(0, "neutral", "walk"), (2, "neutral", "stand")]),
        b("นิติบอกว่า ที่ตรงนั้นติดกล้องอยู่แล้ว", p0, [(2, "neutral", "point")]),
        b("ทายสิ ผมทำยังไงต่อ", p0, [(0, "smug", "stand")], shot="guess"),
        b("ผมยกที่จอดให้เขาเช่าต่อ เดือนละสองพัน", p0, [(0, "smug", "point"), (1, "shock", "arms_up")], shot="twist"),
        b("เขาจอดฟรีมาสามเดือน ก็เลยโดนเก็บย้อนหลัง", p0, [(1, "sad", "stand"), (2, "neutral", "phone")]),
        b("ตอนนี้ผมจอดข้างนอก แต่ได้เงินทุกเดือน กดติดตามไว้นะ", p0, [(0, "happy", "stand")]),
    ]
    return DoodlePlan(topic=topic, title="เพื่อนบ้านแย่งที่จอดตรงผมไม่เลิก ผมเลย…", scenes=scenes,
                      post_caption="เพื่อนบ้านแย่งที่จอดรถผมทุกคืน\nถ้าเป็นคุณจะทำยังไง? คอมเมนต์มาคุยกัน 👇",
                      hashtags=["#ปริศนา60วิ", "#เรื่องเล่า"], hook_title="เพื่อนบ้านแย่งที่จอดตรงผมไม่เลิก ผมเลย…",
                      comment_question="ถ้าเป็นคุณจะทำยังไง?", style="doodle",
                      cast=[{"name": "ผม", "role": "ผมเอง", "hair": "short", "glasses": True, "color": "blue"},
                            {"name": "พี่ห้อง 12", "role": "เพื่อนบ้าน", "hair": "cap", "glasses": False, "color": "red"},
                            {"name": "พี่นิติ", "role": "นิติบุคคล", "hair": "bun", "glasses": True, "color": "green"}],
                      rain=True)
