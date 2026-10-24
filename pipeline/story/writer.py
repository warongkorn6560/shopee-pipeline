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
    "shot": {"type": "string", "enum": ["photo", "map", "year"]},
    "year": _N,
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


SHOWRUNNER = f"""You are the showrunner of "{STORY_SERIES_NAME}", a Thai Facebook/TikTok page that tells \
political history as short documentary episodes: how a political event really happened — the cause, \
the people, the turning point, the consequence — told with real archival photos, a map of where it \
happened, and animated year cards that walk the timeline. A Thai narrator reads your script.

What makes short history videos get shared:
- A hook that reframes something Thai people think they know ("ทำไมรัฐธรรมนูญไทยถึงมีถึง 20 ฉบับ?",
  "นายกฯ คนแรกของไทยอยู่ในตำแหน่งได้นานแค่ไหน?") — a question people want answered and argued about.
- A clear timeline the viewer can follow: one turning point per beat, each with a date and a number.
- Concrete specifics: dates (วัน เดือน พ.ศ.), names and titles, places, counts, durations.
- Plain spoken Thai like a calm documentary host. Short sentences. No filler, no moralising.

Non-negotiable editorial rules (Thai law and fairness):
- Only facts supported by the SOURCE NOTES. If historians disagree, say so in one neutral line.
- Strictly neutral: describe what happened and what each side said; never judge who was right,
  never use loaded words, never endorse or attack a party, movement or person.
- The Thai monarchy is out of scope: do not discuss any king or member of the royal family, their
  actions, roles or opinions. The only allowed mentions are reign names used as neutral time markers
  ("สมัยรัชกาลที่ 7") and the textbook phrase for the 2475 change of government
  ("เปลี่ยนแปลงการปกครองเป็นระบอบประชาธิปไตยอันมีพระมหากษัตริย์ทรงเป็นประมุข").
- No active court cases.
- Living people: only their documented public roles and actions; no claims about motives or character.
- No current election campaigning, no calls to action beyond following the page and commenting.
- No graphic descriptions of violence; state casualty figures only if they are in the notes."""

STORY_PROMPT = """TOPIC: {topic}
ANGLE: {angle}

SOURCE NOTES (Wikipedia):
{notes}

Write the plan for one vertical video of about {seconds} seconds.

BEATS — 7 to 12, in order:
  1. HOOK: the curiosity question on a strong archival photo or year card. ≤ 2 short sentences.
  2. CONTEXT: when and where — usually a map beat or a year card.
  middle beats: the turning points in time order, one per beat, each with its date and one number.
  second-to-last: the consequence / what it changed (often a year card for the end date).
  last: CTA — ask the comment question, then "กดติดตาม{series}ไว้ แล้วมาดูตอนต่อไปกัน".

FIELDS PER BEAT
- narration: what viewers read in subtitles (Thai, numbers as digits OK). Put a space between
  phrases every 8-25 characters, the way Thai is normally spaced, so subtitles break cleanly.
- spoken: the SAME sentence written for text-to-speech: every number, date and unit spelled out in
  Thai words (24 มิ.ย. 2475 → วันที่ยี่สิบสี่ มิถุนายน พุทธศักราชสองพันสี่ร้อยเจ็ดสิบห้า,
  ร.7 → รัชกาลที่เจ็ด), no symbols, no English abbreviations, no emoji.
  All spoken text together: {chars_min}-{chars_max} Thai characters.
- card_title: big title on the card, max 14 characters (a name, an event, or a date).
- card_subtitle: max 34 characters (who / what / where).
- card_fact: max 34 characters, one number fact, or "".
- shot — choose the visual that best proves the sentence:
  "photo": a real archival photo, portrait or document. Set photo_query to 2-5 ENGLISH Wikimedia
     Commons keywords that name it exactly (e.g. "Democracy Monument Bangkok", "Pridi Banomyong",
     "Siamese revolution 1932", "Thai constitution 1932 document"). About half the beats.
  "year": an animated year card for a key date — set year to the Buddhist-era year as a number
     (e.g. 2475) and card_title to the date text ("24 มิ.ย. 2475"). 1-3 per video.
  "map": where it happened — fill focus/labels/spans as below. 1-3 per video.
  Use year = 0 and photo_query = "" when they don't apply.
- focus (map beats): real places/features with names as in OpenStreetMap Thailand (Thai), e.g.
  {{"name": "ถนนราชดำเนินกลาง", "kind": "road", "style": "line", "number": ""}},
  {{"name": "อนุสาวรีย์ประชาธิปไตย", "kind": "place", "style": "pin", "number": "1"}}.
  kind: waterway | road | railway | admin_area | area | place. style: line | area | pin. [] if none.
- labels (map beats): 2-6 Thai place names for orientation. [] otherwise.
- span_start_km / span_end_km (map beats): map width at start/end; city scale ~2-15, country ~600-1200.
  Use 30 and 15 when not a map beat.

REGION: lon/lat box (west, south, east, north) containing the map places (Thailand if none).

ALSO
- title: video title, max 40 characters.
- hook_title (max 14) + hook_subtitle (max 32): the opening card.
- post_caption: 1-2 short curiosity lines for the Facebook post, then the comment question and
  "คอมเมนต์บอกกันหน่อย 👇". Neutral wording. No hashtags here.
- comment_question: an open, neutral question viewers answer (not "who was right").
- hashtags: 5 hashtags starting with #, including #{series_tag}."""

TOPIC_PROMPT = """Series: {series}
Niche: {niche}

Already covered (do not repeat or closely paraphrase):
{previous}

Propose ONE new episode topic. It must be:
- Political history with a clear, well-documented timeline: mostly Thai (constitutions, elections,
  prime ministers' terms, parliament, political parties, key laws, the 2475 change of government,
  historical turning points), sometimes world political history that Thai viewers know.
- At least 15 years in the past, so it is history rather than current politics.
- A curiosity question Thai people want answered ("ทำไม…?", "…เกิดขึ้นได้อย่างไร?", "…มีกี่…?").
- NOT centred on the monarchy or royal family, NOT centred on a living politician, NOT an active court
  case, NOT a current election issue.
Write topic (Thai question, ≤ 70 characters) and angle (one Thai sentence: the timeline the episode
will walk through)."""

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
    year: float = 0.0


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
        "You plan episodes for a neutral Thai political-history page. Every topic is documented history.",
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
        visual=shot if shot in ("photo", "year") else "map",
        image_query=str(b.get("photo_query", "")).strip(),
        card_title=str(b.get("card_title", "")).strip()[:20],
        card_subtitle=str(b.get("card_subtitle", "")).strip()[:44],
        card_fact=str(b.get("card_fact", "")).strip()[:44],
        highlight=str(b.get("card_fact", "")).strip()[:20],
        focus=focus,
        labels=[str(x).strip() for x in (b.get("labels") or []) if str(x).strip()][:6],
        span_start_km=start, span_end_km=end,
        year=_clamp(b.get("year"), 0, 3000, 0),
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


COMPLIANCE_SCHEMA = _obj({"pass": {"type": "boolean"}, "issues": {"type": "array", "items": _S}})
COMPLIANCE_SYSTEM = """You are the standards editor of a Thai political-history page. You check a draft
video script before it is produced and you are strict: when in doubt, fail it."""
COMPLIANCE_PROMPT = """Check this draft against every rule. Fail it if ANY rule is broken.

RULES
1. Monarchy out of scope: no discussion of any king or royal family member, their actions, roles or
   opinions. Allowed only: reign names as time markers ("สมัยรัชกาลที่ 7") and the textbook phrase
   "เปลี่ยนแปลงการปกครองเป็นระบอบประชาธิปไตยอันมีพระมหากษัตริย์ทรงเป็นประมุข".
2. Neutral: no judgement of who was right, no loaded or emotive words, no endorsing or attacking any
   party, movement or person.
3. Living people: only documented public roles/actions; nothing about motives or character.
4. No current election campaigning, no active court cases, no calls to action except follow/comment.
5. No graphic violence.
6. Every factual claim must be plausible for the cited sources: {sources}

DRAFT
Title: {title}
Opening card: {hook}
Beats:
{beats}
Post caption: {caption}

Return pass=true only if every rule holds; otherwise pass=false and list each issue in Thai,
quoting the offending text."""


class ComplianceError(RuntimeError):
    pass


# Deterministic backstop behind the LLM editor, which can miss things, vary between runs, or be the
# weaker AI Gateway fallback. Royal terms outside the allowed phrases fail closed every time.
_ALLOWED_PHRASES = (
    "เปลี่ยนแปลงการปกครองเป็นระบอบประชาธิปไตยอันมีพระมหากษัตริย์ทรงเป็นประมุข",
    "ระบอบประชาธิปไตยอันมีพระมหากษัตริย์ทรงเป็นประมุข",
    "พระราชบัญญัติ", "พระราชกฤษฎีกา", "พระราชกำหนด",
)
_ROYAL_TERMS = (
    "ในหลวง", "พระบาทสมเด็จ", "พระเจ้าอยู่หัว", "กษัตริย์", "สถาบันฯ", "ราชวงศ์", "ราชินี", "ราชกุมาร",
    "เจ้าฟ้า", "พระองค์", "พระบรม", "พระราช", "ทรงพระ", "หมิ่นพระ", "ล้มเจ้า", "ม.112", "มาตรา 112",
    "มาตราหนึ่งร้อยสิบสอง", "ภูมิพล", "วชิราลงกรณ", "สิริกิติ์", "ประชาธิปก", "อานันทมหิดล",
)


def royal_term_hits(plan: "StoryPlan") -> list[str]:
    fields = [plan.title, plan.hook_title, plan.hook_subtitle, plan.post_caption, plan.comment_question,
              " ".join(plan.hashtags)]
    for sc in plan.scenes:
        fields += [sc.narration, sc.spoken, sc.card_title, sc.card_subtitle, sc.card_fact, " ".join(sc.labels)]
    text = " ".join(f for f in fields if f)
    for phrase in _ALLOWED_PHRASES:
        text = text.replace(phrase, " ")
    return [t for t in _ROYAL_TERMS if t in text]


def compliance_review(plan: "StoryPlan") -> tuple[bool, list[str]]:
    hits = royal_term_hits(plan)
    beats = "\n".join(f"{i + 1}. [{s.card_title} | {s.card_subtitle} | {s.card_fact}] {s.narration}"
                      for i, s in enumerate(plan.scenes))
    data = generate_json(
        COMPLIANCE_SYSTEM,
        COMPLIANCE_PROMPT.format(sources=", ".join(plan.sources) or "-", title=plan.title,
                                 hook=f"{plan.hook_title} / {plan.hook_subtitle}", beats=beats,
                                 caption=plan.post_caption),
        schema=COMPLIANCE_SCHEMA, max_tokens=8000, effort="medium", gateway_model="openai/gpt-4.1-mini",
    )
    issues = [str(x) for x in data.get("issues", [])][:8]
    if hits:
        issues.insert(0, "ห้ามมีคำเกี่ยวกับสถาบันพระมหากษัตริย์นอกวลีที่อนุญาต — พบ: " + ", ".join(hits))
    return bool(data.get("pass")) and not hits, issues


def write_reviewed_story(topic: str, angle: str = "") -> "StoryPlan":
    """Write → standards review → one rewrite with the editor's notes → fail closed."""
    plan = write_story(topic, angle)
    ok, issues = compliance_review(plan)
    if ok:
        print("  [review] passed standards check")
        return plan
    print(f"  [review] failed: {issues}")
    plan = write_story(topic, (angle + "\n\nThe previous draft FAILED the standards review for these reasons — "
                               "fix every one:\n- " + "\n- ".join(issues)).strip())
    ok, issues = compliance_review(plan)
    if not ok:
        raise ComplianceError("ไม่ผ่านการตรวจมาตรฐานเนื้อหา: " + " | ".join(issues))
    print("  [review] passed on rewrite")
    return plan


def mock_story(topic: str) -> StoryPlan:
    """Offline plan (no LLM) that exercises every beat type: year, photo (falls back to a card
    offline), map."""
    def b(visual, n, sp, title, sub, fact, *, year=0, focus=(), labels=(), s0=0, s1=0, query=""):
        return StoryScene(narration=n, spoken=sp, card_title=title, card_subtitle=sub, card_fact=fact,
                          caption=title, highlight=fact, visual=visual, year=year, focus=list(focus),
                          labels=list(labels), span_start_km=s0, span_end_km=s1, image_query=query)
    scenes = [
        b("year", "คนไทยเข้าคูหาเลือกตั้งครั้งแรก เมื่อเก้าสิบกว่าปีก่อน แต่ไม่ได้เลือก ส.ส. ตรงอย่างวันนี้",
          "คนไทยเข้าคูหาเลือกตั้งครั้งแรก เมื่อเก้าสิบกว่าปีก่อน แต่ไม่ได้เลือกสอสอตรงอย่างวันนี้",
          "15 พ.ย. 2476", "การเลือกตั้งทั่วไปครั้งแรก", "เลือกตั้งทางอ้อม", year=2476),
        b("photo", "สภาผู้แทนราษฎรชุดแรก ประชุมกันที่พระที่นั่งอนันตสมาคม",
          "สภาผู้แทนราษฎรชุดแรก ประชุมกันที่พระที่นั่งอนันตสมาคม",
          "สภาชุดแรก", "ประชุมที่พระที่นั่งอนันตสมาคม", "", query="Ananta Samakhom Throne Hall"),
        b("map", "ตอนนั้นสยามแบ่งเป็นเจ็ดสิบจังหวัด แต่ละจังหวัดได้ผู้แทนตามจำนวนประชากร",
          "ตอนนั้นสยามแบ่งเป็นเจ็ดสิบจังหวัด แต่ละจังหวัดได้ผู้แทนตามจำนวนประชากร",
          "70 จังหวัด", "ผู้แทน 78 คน", "", labels=["กรุงเทพมหานคร", "เชียงใหม่", "ขอนแก่น", "สงขลา"],
          s0=1600, s1=1100),
        b("year", "สี่ปีต่อมา จึงมีการเลือกตั้ง ส.ส. แบบทางตรงเป็นครั้งแรก",
          "สี่ปีต่อมา จึงมีการเลือกตั้งสอสอแบบทางตรงเป็นครั้งแรก",
          "7 พ.ย. 2480", "เลือกตั้งทางตรงครั้งแรก", "", year=2480),
        b("photo", "คุณคิดว่าการเลือกตั้งครั้งไหนสำคัญที่สุด คอมเมนต์บอกกันหน่อย แล้วกดติดตามไว้",
          "คุณคิดว่าการเลือกตั้งครั้งไหนสำคัญที่สุด คอมเมนต์บอกกันหน่อย แล้วกดติดตามไว้",
          "ครั้งไหนสำคัญสุด?", "คอมเมนต์บอกกันหน่อย", "", query="Thailand parliament 1930s"),
    ]
    return StoryPlan(topic=topic, title="เลือกตั้งครั้งแรกของไทย เลือกกันยังไง", scenes=scenes,
                     post_caption="คนไทยเลือกตั้งครั้งแรกเมื่อ พ.ศ. 2476 แต่ไม่ได้เลือก ส.ส. ตรงอย่างวันนี้\nครั้งไหนสำคัญที่สุด คอมเมนต์บอกกันหน่อย 👇",
                     hashtags=["#ย้อนรอยการเมืองไทย", "#ประวัติศาสตร์การเมือง", "#เลือกตั้ง"],
                     sources=["Wikipedia (ไทย): การเลือกตั้งสมาชิกสภาผู้แทนราษฎรไทยเป็นการทั่วไป พ.ศ. 2476"],
                     hook_title="เลือกตั้งครั้งแรก", hook_subtitle="คนไทยเลือกกันยังไง?",
                     region={"name": "ประเทศไทย", "west": 97.3, "south": 5.6, "east": 105.7, "north": 20.5},
                     comment_question="การเลือกตั้งครั้งไหนสำคัญที่สุด?")
