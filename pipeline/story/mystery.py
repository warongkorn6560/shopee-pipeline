"""
"mystery" theme: original fictional Thai short mysteries (45-75 s), rendered by mystery_render.py.

Structure: hook question → suspects → 2-3 fair, numbered clues → "หยุดดู ทายก่อน!" pause card → twist
reveal that points back at the clues → one-line ending. Everything is fiction ("เรื่องแต่ง").
Code checks the structure (every clue the reveal relies on was shown before the pause); the standards
editor checks the logic (the clues support the answer, and only that answer).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..config import STORY_SERIES_NAME, STORY_TARGET_SECONDS
from ..llm import generate_json
from .writer import CHARS_PER_SECOND, StoryPlan, StoryScene, _obj

_S, _I = {"type": "string"}, {"type": "integer"}

SETTINGS = ("street", "apartment", "mansion", "office", "train", "cafe", "school", "forest")
ICONS = ("key", "clock", "footprint", "cup", "phone", "letter", "umbrella", "ring", "photo", "door", "light", "car")
EMOTIONS = ("neutral", "shock", "think", "worry", "happy", "mindblown")
SHOTS = ("scene", "suspects", "clue", "pause", "reveal", "ending")
FICTION = "เรื่องแต่ง ไม่เกี่ยวข้องกับบุคคลหรือเหตุการณ์จริง"

BEAT_SCHEMA = _obj({
    "narration": _S, "spoken": _S,
    "shot": {"type": "string", "enum": list(SHOTS)},
    "clue_number": _I, "clue_text": _S,
    "clue_icon": {"type": "string", "enum": list(ICONS)},
    "focus_suspect": _I,
    "emotion": {"type": "string", "enum": list(EMOTIONS)},
    "punch": _S,
})
STORY_SCHEMA = _obj({
    "title": _S, "hook_title": _S, "hook_subtitle": _S,
    "setting": {"type": "string", "enum": list(SETTINGS)},
    "suspects": {"type": "array", "items": _obj({"name": _S, "role": _S})},
    "answer_suspect": _I,
    "explanation": _S,
    "beats": {"type": "array", "items": BEAT_SCHEMA},
    "post_caption": _S, "comment_question": _S,
    "hashtags": {"type": "array", "items": _S},
})

SHOWRUNNER = f"""You write "{STORY_SERIES_NAME}", a Thai Instagram/TikTok/Facebook series of original 60-second \
mysteries. Each episode is a small, clever puzzle — a missing item, a locked room, an alibi that doesn't add \
up — told by a calm late-night narrator over dark, moody visuals. Viewers try to solve it before the reveal \
and argue in the comments.

What makes them addictive:
- A hook in the first 3 seconds that poses the puzzle ("ใครขโมยแหวนในห้องที่ล็อกจากข้างใน?").
- Fair play: every clue needed to solve it is shown on screen BEFORE the pause, numbered. No hidden facts
  in the reveal. A sharp viewer can get it.
- A twist that reframes an innocent-looking clue — the "อ๋อ!" moment.
- Short, tense spoken Thai. Present tense. Concrete details (times, objects, weather).

Rules:
- Pure fiction with invented everyday Thai names (e.g. "คุณมานพ", "ป้าแดง"). No real people, celebrities,
  brands, real crimes, real victims or real places tied to crimes.
- Platform-safe: thefts, pranks, lies, lost items, swaps, small frauds. No murder, no weapons, no blood,
  no kidnapping, no self-harm, no sexual content, nothing involving harm to children or animals.
- Nobody is mocked for gender, ethnicity, religion, disability or class. No police procedure claims."""

STORY_PROMPT = """PREMISE: {topic}
NOTES: {angle}

Write one vertical episode of about {seconds} seconds.

CAST: 2-4 suspects (name ≤ 12 characters, role ≤ 16 characters, e.g. "แม่บ้าน", "ลูกชายคนเล็ก").
answer_suspect: the index (0-based) of the one who did it, or -1 if the answer is not a person
(e.g. the cat, the wind) — then say what it was in the explanation.

BEATS — 8 to 11, in this order:
  1. "scene": HOOK — the puzzle as a question, ≤ 2 short sentences. punch = 2-4 words.
  2. "scene" or "suspects": what happened, when, where.
  3. "suspects": introduce everyone (focus_suspect = -1).
  4-6. "clue" × 2-3: one clue per beat, clue_number 1, 2, 3 in order. clue_text ≤ 26 characters is the
     evidence tag ("แก้วกาแฟยังอุ่น", "รองเท้าเปียกแค่ข้างเดียว"); narration describes it naturally.
     A suspect's statement can be a clue. Include one red herring if it fits, but the answer must follow
     from the clues alone.
  then "pause": "หยุดดูก่อน! ทายสิ … คอมเมนต์คำตอบไว้" style, counting down สาม สอง หนึ่ง.
  then "reveal" × 1-2: name the answer and walk back through the clues by number (clue_number = the clue
     being explained, focus_suspect = answer_suspect). No new evidence.
  last "ending": one line that lands the twist, then "กดติดตาม{series}ไว้ คืนพรุ่งนี้มีคดีใหม่".

FIELDS PER BEAT
- narration: subtitle text, spaces between phrases every 8-25 characters.
- spoken: the SAME sentence for text-to-speech, numbers and times in Thai words, no symbols or emoji.
  All spoken text together: {chars_min}-{chars_max} Thai characters.
- clue_number: 1-3 on clue/reveal beats, 0 otherwise. clue_text: "" unless shot is "clue".
- clue_icon: the object that best pictures the clue (any value when not a clue).
- focus_suspect: the suspect this beat is about, -1 for none.
- emotion: the narrator owl's reaction — think, shock, worry, mindblown (the reveal), happy, neutral.
- punch: 2-4 words ≤ 16 characters slammed on screen, or "".

ALSO
- setting: where it happens: {settings}.
- explanation: 2-3 Thai sentences proving the answer from clues by number.
- title (≤ 40), hook_title (≤ 14), hook_subtitle (≤ 32).
- post_caption: the puzzle in 1-2 lines (no spoilers), the comment question, "คอมเมนต์คำตอบกันมา 👇". No hashtags.
- comment_question: "ใครคือคนร้าย?" style, no spoiler.
- hashtags: 5 hashtags starting with #, including #{series_tag}."""

@dataclass
class MysteryPlan(StoryPlan):
    setting: str = "street"
    suspects: list[dict] = field(default_factory=list)
    answer_suspect: int = -1
    explanation: str = ""


def _int(v, lo, hi, default):
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return default


def _scene(b: dict, n_suspects: int) -> StoryScene:
    shot = b.get("shot") if b.get("shot") in SHOTS else "scene"
    sc = StoryScene(
        narration=str(b.get("narration", "")).strip(),
        spoken=str(b.get("spoken", "")).strip() or str(b.get("narration", "")).strip(),
        visual=shot,
        emotion=b.get("emotion") if b.get("emotion") in EMOTIONS else "neutral",
        punch=str(b.get("punch", "")).strip()[:20],
        card_title=str(b.get("clue_text", "")).strip()[:30] if shot == "clue" else "",
    )
    sc.clue = _int(b.get("clue_number"), 0, 3, 0) if shot in ("clue", "reveal") else 0
    sc.icon = b.get("clue_icon") if b.get("clue_icon") in ICONS else "photo"
    sc.focus = _int(b.get("focus_suspect"), -1, n_suspects - 1, -1)
    return sc


def structure_issues(plan: MysteryPlan) -> list[str]:
    shots = [s.visual for s in plan.scenes]
    issues = []
    if "pause" not in shots:
        return ["ต้องมีฉาก pause (หยุดดู ทายก่อน) ก่อนเฉลย"]
    p = shots.index("pause")
    clues = [s.clue for s in plan.scenes[:p] if s.visual == "clue"]
    if len(clues) < 2:
        issues.append("ต้องมีเบาะแสอย่างน้อย 2 ข้อก่อน pause")
    if any(s.visual == "clue" for s in plan.scenes[p:]):
        issues.append("ห้ามมีเบาะแสใหม่หลัง pause")
    if "reveal" not in shots[p:]:
        issues.append("ต้องมีฉาก reveal หลัง pause")
    missing = sorted({s.clue for s in plan.scenes[p:] if s.visual == "reveal" and s.clue and s.clue not in clues})
    if missing:
        issues.append(f"เฉลยอ้างเบาะแสข้อ {missing} ที่ไม่ได้แสดงก่อน pause")
    if not 2 <= len(plan.suspects) <= 4:
        issues.append("ต้องมีผู้ต้องสงสัย 2-4 คน")
    return issues


def write_mystery(topic: str, angle: str = "") -> MysteryPlan:
    seconds = min(STORY_TARGET_SECONDS, 70)
    feedback = angle
    for attempt in range(3):
        data = generate_json(
            SHOWRUNNER,
            STORY_PROMPT.format(topic=topic, angle=feedback or "-", seconds=seconds,
                                chars_min=int(seconds * CHARS_PER_SECOND * 0.85),
                                chars_max=int(seconds * CHARS_PER_SECOND * 1.1), settings=", ".join(SETTINGS),
                                series=STORY_SERIES_NAME, series_tag=STORY_SERIES_NAME.replace(" ", "")),
            schema=STORY_SCHEMA, max_tokens=24000, gateway_model="openai/gpt-4.1-mini",
        )
        suspects = [{"name": str(x.get("name", "")).strip()[:16], "role": str(x.get("role", "")).strip()[:20]}
                    for x in data.get("suspects") or [] if str(x.get("name", "")).strip()][:4]
        scenes = [_scene(b, max(len(suspects), 1)) for b in data.get("beats", [])
                  if str(b.get("narration", "")).strip()][:12]
        if len(scenes) < 6:
            raise RuntimeError(f"Mystery plan too short ({len(scenes)} beats).")
        plan = MysteryPlan(
            topic=topic, title=str(data.get("title", topic)).strip()[:60], scenes=scenes,
            post_caption=str(data.get("post_caption", "")).strip(),
            hashtags=[h for h in data.get("hashtags", []) if str(h).startswith("#")][:6],
            sources=[], hook_title=str(data.get("hook_title", "")).strip()[:20],
            hook_subtitle=str(data.get("hook_subtitle", "")).strip()[:40],
            comment_question=str(data.get("comment_question", "")).strip(), style="mystery",
            setting=data.get("setting") if data.get("setting") in SETTINGS else "street",
            suspects=suspects, answer_suspect=_int(data.get("answer_suspect"), -1, len(suspects) - 1, -1),
            explanation=str(data.get("explanation", "")).strip(),
        )
        issues = structure_issues(plan)
        if not issues:
            return plan
        print(f"  [mystery] structure (attempt {attempt + 1}): {issues}")
        feedback = (angle + "\n\nThe previous draft broke the episode structure — fix every one:\n- "
                    + "\n- ".join(issues)).strip()
    raise RuntimeError("โครงเรื่องปริศนาไม่ครบ: " + " | ".join(issues))


def mock_mystery(topic: str) -> MysteryPlan:
    """Offline plan (no LLM) for render tests."""
    def b(shot, n, *, clue=0, text="", icon="photo", focus=-1, emo="think", punch=""):
        return _scene({"narration": n, "spoken": n, "shot": shot, "clue_number": clue, "clue_text": text,
                       "clue_icon": icon, "focus_suspect": focus, "emotion": emo, "punch": punch}, 3)
    scenes = [
        b("scene", "ตีสองคืนฝนตก แหวนเพชรหายจากห้องที่ล็อกจากข้างใน ใครเอาไป?", emo="shock", punch="แหวนหาย!"),
        b("suspects", "คืนนั้นในบ้านมีแค่สามคน แม่บ้าน ลูกชาย และคนขับรถ"),
        b("clue", "หลักฐานแรก พรมหน้าห้องเปียก เป็นรอยรองเท้าแค่ข้างเดียว", clue=1, text="รอยเท้าเปียกข้างเดียว",
          icon="footprint"),
        b("clue", "หลักฐานที่สอง ร่มของคนขับรถยังแห้งสนิท ทั้งที่เขาบอกว่าเพิ่งกลับจากข้างนอก", clue=2,
          text="ร่มยังแห้งสนิท", icon="umbrella", focus=2),
        b("clue", "หลักฐานที่สาม ลูกชายเพิ่งเข้าเฝือกขาขวาเมื่อวาน", clue=3, text="ขาขวาเข้าเฝือก", icon="door",
          focus=1, emo="worry"),
        b("pause", "หยุดดูก่อน ทายสิ ใครเอาแหวนไป คอมเมนต์คำตอบไว้ สาม สอง หนึ่ง", emo="think"),
        b("reveal", "คำตอบคือลูกชาย รอยเท้าข้างเดียว เพราะอีกข้างคือเฝือก", clue=1, focus=1, emo="mindblown",
          punch="ลูกชาย!"),
        b("reveal", "ส่วนร่มที่แห้ง คนขับรถแค่โกหกว่าออกไปข้างนอก แต่ไม่ได้ขโมย", clue=2, focus=1),
        b("ending", "บางครั้งคนที่ดูไม่น่าสงสัยที่สุด ก็ทิ้งรอยไว้ชัดที่สุด กดติดตามไว้ คืนพรุ่งนี้มีคดีใหม่", emo="happy"),
    ]
    return MysteryPlan(topic=topic, title="แหวนหายในห้องที่ล็อกจากข้างใน", scenes=scenes,
                       post_caption="ตีสอง ฝนตก แหวนเพชรหายจากห้องที่ล็อกจากข้างใน\nใครเอาไป? คอมเมนต์คำตอบกันมา 👇",
                       hashtags=["#ปริศนา60วิ", "#ปริศนา", "#เรื่องสั้น"], hook_title="แหวนหาย ตีสอง",
                       hook_subtitle="ห้องล็อกจากข้างใน", comment_question="ใครเอาแหวนไป?", style="mystery",
                       setting="mansion",
                       suspects=[{"name": "ป้าแดง", "role": "แม่บ้าน"}, {"name": "ต้น", "role": "ลูกชาย"},
                                 {"name": "ลุงชัย", "role": "คนขับรถ"}],
                       answer_suspect=1, explanation="รอยเท้าข้างเดียว (1) ตรงกับคนเข้าเฝือก (3)")
