"""
"money" theme: what-if money/business micro-stories ("เปิดร้านชาเย็นหน้าโรงเรียน 10 วัน",
"เก็บวันละ 100 บาท 10 ปี") rendered in the "sim" style (sim_render.py).

Two Claude calls, with the arithmetic in between done here, never by the model:
  1. design  — the scenario as parameters (prices, daily sales, deposits, rates), each real-world
               figure tied to the research notes, everything else marked as an assumption
  2. compute — this module turns the parameters into a step-by-step table (day/month/year)
  3. script  — beats written against that table; every number on screen or in the narration must
               come from the table, the parameters or the notes (checked in code, rewrite on failure)
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from ..config import STORY_NICHE, STORY_SERIES_NAME, STORY_TARGET_SECONDS
from ..llm import generate_json
from .writer import CHARS_PER_SECOND, StoryPlan, StoryScene, _obj, research

_S, _N, _I = {"type": "string"}, {"type": "number"}, {"type": "integer"}

SETTINGS = ("stall", "school", "market", "home", "bank", "office", "street")
EMOTIONS = ("neutral", "shock", "think", "worry", "happy", "mindblown")
DISCLAIMER = "สถานการณ์จำลองเพื่อการเรียนรู้ ไม่ใช่คำแนะนำการลงทุน"

# ---------------------------------------------------------------------------
# 1. Scenario design
# ---------------------------------------------------------------------------
DESIGN_SCHEMA = _obj({
    "model": {"type": "string", "enum": ["shop", "savings", "installment"]},
    "product": _S,                  # shop: what is sold ("ชาเย็น")
    "unit": _S,                     # shop: unit word ("แก้ว")
    "start_cost": _N,               # shop: upfront spend before day 1 (cart, equipment)
    "fixed_cost_per_day": _N,       # shop: rent/ice/gas per day
    "unit_cost": _N,                # shop: ingredient cost per unit
    "days": {"type": "array", "items": _obj({"price": _N, "units": _I, "event": _S})},
    "competitor_price": _N,         # shop: the rival's price, 0 if none
    "deposit": _N,                  # savings: amount put in each period
    "every": {"type": "string", "enum": ["day", "month"]},
    "years": _I,                    # savings
    "rate_pct": _N,                 # savings: annual interest (%), installment: flat rate per year (%)
    "compare_rate_pct": _N,         # savings: a second line to compare (e.g. 0 = piggy bank), -1 if none
    "principal": _N,                # installment: price of the thing bought
    "months": _I,                   # installment
    "assumptions": {"type": "array", "items": _S},
    "sourced_facts": {"type": "array", "items": _obj({"fact": _S, "source": _S})},
})

DESIGN_SYSTEM = f"""You design the scenario behind one episode of "{STORY_SERIES_NAME}", a Thai page of \
what-if money and small-business simulations. Viewers watch a cartoon piggy-bank mascot run the scenario \
day by day while a counter shows the money. You only set the inputs; the program does every calculation.

Rules:
- Realistic Thai numbers (baht). Prices and costs must be believable for Thailand today.
- A real-world figure (an interest rate, a typical price, a minimum wage) is allowed only if it is in the
  SOURCE NOTES; list it in sourced_facts with the source label. Every other number is an assumption of the
  simulation: list each in plain Thai in assumptions (e.g. "สมมติขายได้วันละ 40 แก้ว").
- No real company, brand, shop, stock, fund, coin or person. No gambling, no lottery, no crypto, no
  get-rich-quick, no guaranteed returns.
- The scenario must have a twist the viewer learns from (a price war, hidden costs, the power of compound
  interest, the true cost of installments)."""

DESIGN_PROMPT = """TOPIC: {topic}
ANGLE: {angle}

SOURCE NOTES (Wikipedia):
{notes}

Choose model and fill its fields (use 0, "" or [] for fields of the other models):
- "shop": a small business over 3-15 days. days = one entry per day in order: the price charged that
  day, units sold, and a short Thai event ("ร้านข้างๆ ลดราคา", "ฝนตก", "" if nothing). start_cost,
  fixed_cost_per_day, unit_cost, competitor_price (0 if no rival), product, unit.
- "savings": deposit every "day" or "month" for 1-40 years at rate_pct a year (compounded monthly);
  compare_rate_pct for a second line (0 = kept at home, -1 = no comparison).
- "installment": buy something for principal baht over months at a flat rate_pct per year.
assumptions: 2-6 short Thai lines. sourced_facts: [] if none."""

# ---------------------------------------------------------------------------
# 2. Compute
# ---------------------------------------------------------------------------
@dataclass
class Step:
    label: str                       # "วันที่ 3", "ปีที่ 10", "เดือนที่ 6"
    value: float                     # the main counter (cumulative profit, balance, amount paid)
    delta: float = 0.0               # change this step (today's profit, …)
    second: float | None = None      # comparison line (savings) — balance at compare_rate_pct
    price: float = 0.0               # shop: price charged that day
    units: int = 0
    event: str = ""


@dataclass
class Sim:
    model: str
    counter_label: str               # "กำไรสะสม", "เงินในบัญชี", "จ่ายไปแล้ว"
    step_word: str                   # "วันที่", "ปีที่", "เดือนที่"
    steps: list[Step]
    params: dict
    facts: dict = field(default_factory=dict)       # named results for the script ("total_deposit": …)
    second_label: str = ""
    assumptions: list[str] = field(default_factory=list)
    sourced: list[dict] = field(default_factory=list)

    def table(self) -> str:
        rows = []
        for k, s in enumerate(self.steps):
            extra = (f" · ราคา ฿{fmt(s.price)} ขาย {s.units} · วันนี้ {sign(s.delta)}" if self.model == "shop" else
                     f" · ปีนี้ +฿{fmt(s.delta)}" if self.model == "savings" and k else "")
            if s.second is not None:
                extra += f" · {self.second_label} ฿{fmt(s.second)}"
            rows.append(f"step {k}: {s.label} · {self.counter_label} ฿{fmt(s.value)}{extra}"
                        + (f" · เหตุการณ์: {s.event}" if s.event else ""))
        facts = "\n".join(f"- {k}: {fmt(v) if isinstance(v, (int, float)) else v}" for k, v in self.facts.items())
        return "\n".join(rows) + "\n\nRESULTS\n" + facts


def fmt(v: float) -> str:
    v = round(v, 2)
    return f"{v:,.0f}" if abs(v - round(v)) < 0.005 else f"{v:,.2f}"


def sign(v: float) -> str:
    return ("+" if v >= 0 else "-") + "฿" + fmt(abs(v))


def _num(d: dict, k: str, lo: float, hi: float, default: float = 0.0) -> float:
    try:
        v = float(d.get(k, default))
    except (TypeError, ValueError):
        return default
    return default if math.isnan(v) else max(lo, min(hi, v))


def compute(d: dict) -> Sim:
    model = d.get("model", "shop")
    params = {"assumptions": [str(a) for a in d.get("assumptions") or []][:6],
              "sourced": [f for f in d.get("sourced_facts") or [] if isinstance(f, dict)][:4]}
    if model == "savings":
        deposit = _num(d, "deposit", 1, 1e6, 100)
        every = d.get("every") if d.get("every") in ("day", "month") else "day"
        years = int(_num(d, "years", 1, 40, 10))
        rate = _num(d, "rate_pct", 0, 15)
        cmp_rate = _num(d, "compare_rate_pct", -1, 15, -1)
        per_month = deposit * (30 if every == "day" else 1)

        def balance(r: float, months: int) -> float:
            b, m = 0.0, r / 100 / 12
            for _ in range(months):
                b = (b + per_month) * (1 + m)
            return b

        steps = [Step("เริ่ม", 0.0, second=0.0 if cmp_rate >= 0 else None)]
        for y in range(1, years + 1):
            v = balance(rate, y * 12)
            steps.append(Step(f"ปีที่ {y}", v, v - steps[-1].value,
                              second=balance(cmp_rate, y * 12) if cmp_rate >= 0 else None))
        total_in = per_month * 12 * years
        facts = {"deposit": deposit, "deposit_per_month": per_month, "years": years, "rate_pct": rate,
                 "total_deposit": total_in, "final_balance": steps[-1].value,
                 "interest_earned": steps[-1].value - total_in}
        if cmp_rate >= 0:
            facts |= {"compare_rate_pct": cmp_rate, "compare_final": steps[-1].second,
                      "difference": steps[-1].value - steps[-1].second}
        return Sim("savings", "เงินในบัญชี", "ปีที่", steps, {**d, **params}, facts,
                   second_label=("เก็บไว้เฉยๆ" if cmp_rate == 0 else f"ดอกเบี้ย {fmt(cmp_rate)}%"),
                   assumptions=params["assumptions"], sourced=params["sourced"])

    if model == "installment":
        principal = _num(d, "principal", 100, 5e6, 10000)
        months = int(_num(d, "months", 1, 84, 12))
        rate = _num(d, "rate_pct", 0, 40)
        interest = principal * rate / 100 * months / 12
        monthly = (principal + interest) / months
        steps = [Step("เริ่ม", 0.0)] + [Step(f"เดือนที่ {m}", monthly * m, monthly) for m in range(1, months + 1)]
        facts = {"principal": principal, "months": months, "flat_rate_pct": rate, "monthly_payment": monthly,
                 "total_paid": principal + interest, "total_interest": interest}
        return Sim("installment", "จ่ายไปแล้ว", "เดือนที่", steps, {**d, **params}, facts,
                   assumptions=params["assumptions"], sourced=params["sourced"])

    days = [x for x in d.get("days") or [] if isinstance(x, dict)][:15] or [{"price": 20, "units": 30, "event": ""}]
    start = _num(d, "start_cost", 0, 1e6)
    fixed = _num(d, "fixed_cost_per_day", 0, 1e5)
    unit_cost = _num(d, "unit_cost", 0, 1e4)
    steps = [Step("ก่อนเปิดร้าน", -start)]
    revenue = units_total = 0.0
    for k, day in enumerate(days, 1):
        price, units = _num(day, "price", 0, 1e4), int(_num(day, "units", 0, 1e5))
        profit = price * units - unit_cost * units - fixed
        revenue += price * units
        units_total += units
        steps.append(Step(f"วันที่ {k}", steps[-1].value + profit, profit, price=price, units=units,
                          event=str(day.get("event", "")).strip()[:40]))
    best = max(steps[1:], key=lambda s: s.delta)
    worst = min(steps[1:], key=lambda s: s.delta)
    facts = {"days": len(days), "start_cost": start, "fixed_cost_per_day": fixed, "unit_cost": unit_cost,
             "competitor_price": _num(d, "competitor_price", 0, 1e4), "total_revenue": revenue,
             "total_units": units_total, "final_profit": steps[-1].value,
             "best_day": f"{best.label} ({sign(best.delta)})", "worst_day": f"{worst.label} ({sign(worst.delta)})"}
    breakeven = next((s.label for s in steps[1:] if s.value >= 0), "ยังไม่คืนทุน")
    facts["breakeven"] = breakeven
    return Sim("shop", "กำไรสะสม", "วันที่", steps,
               {**d, **params, "product": str(d.get("product", "")).strip()[:20],
                "unit": str(d.get("unit", "")).strip()[:10]}, facts,
               assumptions=params["assumptions"], sourced=params["sourced"])


# ---------------------------------------------------------------------------
# 3. Script
# ---------------------------------------------------------------------------
SIM_BEAT_SCHEMA = _obj({
    "narration": _S, "spoken": _S,
    "shot": {"type": "string", "enum": ["scene", "versus", "chart", "lesson"]},
    "step": _I,
    "setting": {"type": "string", "enum": list(SETTINGS)},
    "emotion": {"type": "string", "enum": list(EMOTIONS)},
    "punch": _S,
    "versus_left": _S, "versus_left_label": _S, "versus_right": _S, "versus_right_label": _S,
})
SIM_STORY_SCHEMA = _obj({
    "title": _S, "hook_title": _S, "hook_subtitle": _S,
    "beats": {"type": "array", "items": SIM_BEAT_SCHEMA},
    "lesson": _S,
    "post_caption": _S, "comment_question": _S,
    "hashtags": {"type": "array", "items": _S},
})

SIM_SHOWRUNNER = f"""You are the showrunner of "{STORY_SERIES_NAME}", a Thai Facebook/Instagram/TikTok page of \
45-60 second what-if money simulations. A cute piggy-bank mascot called "น้องออม" acts out the scenario; a \
counter shows the money after every step; price-war cards slam in ("฿30 VS ฿15"); the episode ends on one \
lesson line. A Thai narrator reads your script.

What makes these shared: a hook that dares the viewer to guess ("ถ้าเก็บวันละ 100 บาท 10 ปี จะมีเท่าไหร่?"),
fast pacing (one step per beat), a twist in the middle, and a lesson people want to send to a friend.
Plain, lively spoken Thai, short sentences.

Rules:
- It is a simulation: say "สมมติ" for assumptions; never present the result as a promise or advice.
- Every number you write must come from the SIMULATION TABLE, the SCENARIO or the SOURCE NOTES — copy it
  exactly as written there (you may round only when you say "ประมาณ"). Never compute a new number.
- No real brands, shops, people, stocks, funds or coins. No gambling, lottery, crypto, or get-rich-quick.
- No recommendation to buy a financial product; general habits (saving, comparing prices, counting costs)
  are fine."""

SIM_STORY_PROMPT = """TOPIC: {topic}
ANGLE: {angle}

SCENARIO
{scenario}

SIMULATION TABLE (computed by the program — the only source of results)
{table}

SOURCE NOTES (Wikipedia):
{notes}

Write the plan for one vertical video of about {seconds} seconds.

BEATS — 7 to 10, in order:
  1. HOOK: a guess-the-number question ≤ 2 short sentences, step 0.
  2. SETUP: the starting situation and the key assumption (say "สมมติ").
  middle: walk the table forward — each beat moves to a later step and says what happened; include the
     twist (rival, hidden cost, compound growth kicking in). Use "versus" once if there are two prices or
     two outcomes to compare, and "chart" once to show the whole curve.
  second-to-last: the result (the final row) and what surprised us.
  last: "lesson" — the one-line lesson, then the comment question and "กดติดตาม{series}ไว้ แล้วมาลองกันต่อ".

FIELDS PER BEAT
- narration: subtitle text (Thai, digits OK, spaces between phrases every 8-25 characters).
- spoken: the SAME sentence for text-to-speech, every number spelled out in Thai words
  (฿1,250 → หนึ่งพันสองร้อยห้าสิบบาท, 2.5% → สองจุดห้าเปอร์เซ็นต์), no symbols or emoji.
  All spoken text together: {chars_min}-{chars_max} Thai characters.
- shot: "scene" (the mascot in a setting), "versus" (two big cards), "chart" (the curve so far),
  "lesson" (the lesson card; last beat only).
- step: which table row the counter shows during this beat (0-{last_step}); never go backwards.
- setting: where the mascot is: {settings}.
- emotion: the mascot's reaction — happy (money up), worry (money down), shock (surprising number),
  think (a question), mindblown (the big reveal, 1-2 times), neutral.
- punch: 2-4 Thai words ≤ 16 characters slammed on screen (e.g. "ขาดทุน!", "฿30 VS ฿15", "ดอกเบี้ยทบต้น"),
  or "".
- versus_left / versus_right: short card values ≤ 10 characters (e.g. "฿30", "฿15"), with labels
  ≤ 14 characters (e.g. "ร้านเรา", "ร้านข้างๆ"); "" unless shot is "versus".

ALSO
- title (≤ 40 chars), hook_title (≤ 14) + hook_subtitle (≤ 32).
- lesson: the lesson line, ≤ 40 characters.
- post_caption: 1-2 curiosity lines, the comment question, then "คอมเมนต์บอกกันหน่อย 👇". No hashtags.
- comment_question: a question viewers answer with their own guess or experience.
- hashtags: 5 hashtags starting with #, including #{series_tag}."""

@dataclass
class SimPlan(StoryPlan):
    sim: Sim | None = None
    lesson: str = ""
    assumptions: list[str] = field(default_factory=list)


_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _numbers(text: str) -> set[str]:
    return {m.group().replace(",", "").rstrip(".") for m in _NUM.finditer(text or "")}


def _variants(v) -> set[str]:
    if isinstance(v, str):
        return _numbers(v)
    try:
        v = float(v)
    except (TypeError, ValueError):
        return set()
    out = {fmt(v).replace(",", ""), str(int(round(v))), f"{v:.1f}".rstrip("0").rstrip("."), str(int(v))}
    for unit in (1e3, 1e6):                     # "1.2 ล้าน", "15 พัน" style rounding
        if abs(v) >= unit:
            out |= {f"{v / unit:.0f}", f"{v / unit:.1f}".rstrip("0").rstrip(".")}
    return out


def allowed_numbers(sim: Sim, notes_text: str) -> set[str]:
    ok = _numbers(notes_text) | {str(k) for k in range(0, 13)}
    for s in sim.steps:
        ok |= _numbers(s.label) | _variants(s.value) | _variants(abs(s.value)) | _variants(abs(s.delta))
        ok |= _variants(s.price) | _variants(s.units)
        if s.second is not None:
            ok |= _variants(s.second) | _variants(abs(s.value - s.second))
    for v in sim.facts.values():
        ok |= _variants(v) | (_variants(abs(v)) if isinstance(v, (int, float)) else set())
    for k, v in sim.params.items():
        if isinstance(v, (int, float)):
            ok |= _variants(v)
        elif isinstance(v, list):
            ok |= _numbers(" ".join(str(x) for x in v))
    for day in sim.params.get("days") or []:
        if isinstance(day, dict):
            ok |= _variants(day.get("price", 0)) | _variants(day.get("units", 0))
    return ok


def number_issues(plan: SimPlan, ok: set[str]) -> list[str]:
    fields = [plan.title, plan.hook_title, plan.hook_subtitle, plan.lesson, plan.post_caption]
    for sc in plan.scenes:
        fields += [sc.narration, sc.punch, sc.card_title, sc.card_subtitle]
    bad = sorted({n for f in fields for n in _numbers(f) if n not in ok and n.lstrip("0") not in ok})
    return [f"ตัวเลข {n} ไม่มีในตารางจำลอง/ข้อมูลอ้างอิง — ใช้เฉพาะตัวเลขจากตาราง" for n in bad[:6]]


def _scene(b: dict, last: int) -> StoryScene:
    shot = b.get("shot") if b.get("shot") in ("scene", "versus", "chart", "lesson") else "scene"
    vs = (str(b.get("versus_left", "")).strip()[:12], str(b.get("versus_left_label", "")).strip()[:16],
          str(b.get("versus_right", "")).strip()[:12], str(b.get("versus_right_label", "")).strip()[:16])
    try:
        step = max(0, min(last, int(b.get("step", 0))))
    except (TypeError, ValueError):
        step = 0
    sc = StoryScene(
        narration=str(b.get("narration", "")).strip(),
        spoken=str(b.get("spoken", "")).strip() or str(b.get("narration", "")).strip(),
        visual=shot,
        emotion=b.get("emotion") if b.get("emotion") in EMOTIONS else "neutral",
        punch=str(b.get("punch", "")).strip()[:20],
        place=b.get("setting") if b.get("setting") in SETTINGS else "street",   # reused: the drawn setting
        card_title=" VS ".join(x for x in (vs[0], vs[2]) if x),
        card_subtitle=" / ".join(x for x in (vs[1], vs[3]) if x),
    )
    sc.step, sc.versus = step, vs                    # sim-only attributes read by sim_render
    return sc


def design(topic: str, angle: str, notes_text: str) -> Sim:
    data = generate_json(DESIGN_SYSTEM, DESIGN_PROMPT.format(topic=topic, angle=angle or "-", notes=notes_text),
                         schema=DESIGN_SCHEMA, max_tokens=8000, gateway_model="openai/gpt-4.1-mini")
    sim = compute(data)
    print(f"  [sim] {sim.model}: {len(sim.steps)} steps · {sim.facts}")
    return sim


def _scenario_text(sim: Sim) -> str:
    p = sim.params
    if sim.model == "shop":
        head = (f"ร้านขาย{p.get('product', '')} · ทุนเริ่มต้น ฿{fmt(sim.facts['start_cost'])} · "
                f"ต้นทุนต่อ{p.get('unit', 'ชิ้น')} ฿{fmt(sim.facts['unit_cost'])} · ค่าใช้จ่ายคงที่วันละ "
                f"฿{fmt(sim.facts['fixed_cost_per_day'])}"
                + (f" · ร้านคู่แข่งขาย ฿{fmt(sim.facts['competitor_price'])}" if sim.facts["competitor_price"] else ""))
    elif sim.model == "savings":
        head = (f"ฝาก ฿{fmt(sim.facts['deposit'])} ทุก{'วัน' if p.get('every') == 'day' else 'เดือน'} "
                f"{sim.facts['years']} ปี · ดอกเบี้ย {fmt(sim.facts['rate_pct'])}% ต่อปี ทบต้นรายเดือน")
    else:
        head = (f"ผ่อนของราคา ฿{fmt(sim.facts['principal'])} {sim.facts['months']} เดือน · ดอกเบี้ยคงที่ "
                f"{fmt(sim.facts['flat_rate_pct'])}% ต่อปี")
    lines = [head, "สมมติฐาน: " + " · ".join(sim.assumptions or ["-"])]
    lines += [f"ข้อมูลจริง: {f.get('fact', '')} ({f.get('source', '')})" for f in sim.sourced]
    return "\n".join(lines)


def write_sim_story(topic: str, angle: str = "") -> SimPlan:
    notes = research(topic, angle)
    notes_text = "\n\n".join(f"[{label}]\n{text}" for label, text in notes) or "(no notes found)"
    sim = design(topic, angle.split("\n\nThe previous draft")[0], notes_text)
    ok = allowed_numbers(sim, notes_text)
    seconds = min(STORY_TARGET_SECONDS, 58)
    feedback = angle
    for attempt in range(3):
        data = generate_json(
            SIM_SHOWRUNNER,
            SIM_STORY_PROMPT.format(topic=topic, angle=feedback or "-", scenario=_scenario_text(sim),
                                    table=sim.table(), notes=notes_text, seconds=seconds,
                                    chars_min=int(seconds * CHARS_PER_SECOND * 0.85),
                                    chars_max=int(seconds * CHARS_PER_SECOND * 1.1),
                                    last_step=len(sim.steps) - 1, settings=", ".join(SETTINGS),
                                    series=STORY_SERIES_NAME, series_tag=STORY_SERIES_NAME.replace(" ", "")),
            schema=SIM_STORY_SCHEMA, max_tokens=24000, gateway_model="openai/gpt-4.1-mini",
        )
        last = len(sim.steps) - 1
        scenes = [_scene(b, last) for b in data.get("beats", []) if str(b.get("narration", "")).strip()][:12]
        if len(scenes) < 5:
            raise RuntimeError(f"Sim plan too short ({len(scenes)} beats).")
        for a, b in zip(scenes, scenes[1:]):               # the counter never runs backwards
            b.step = max(b.step, a.step)
        plan = SimPlan(
            topic=topic, title=str(data.get("title", topic)).strip()[:60], scenes=scenes,
            post_caption=str(data.get("post_caption", "")).strip(),
            hashtags=[h for h in data.get("hashtags", []) if str(h).startswith("#")][:6],
            sources=[label for label, _ in notes],
            hook_title=str(data.get("hook_title", "")).strip()[:20],
            hook_subtitle=str(data.get("hook_subtitle", "")).strip()[:40],
            comment_question=str(data.get("comment_question", "")).strip(),
            style="sim", sim=sim, lesson=str(data.get("lesson", "")).strip()[:60],
            assumptions=sim.assumptions,
        )
        issues = number_issues(plan, ok)
        if not issues:
            return plan
        print(f"  [sim] numbers not from the table (attempt {attempt + 1}): {issues}")
        feedback = (angle + "\n\nThe previous draft used numbers that are not in the table — fix every one "
                    "(copy numbers exactly from the table, or drop them):\n- " + "\n- ".join(issues)).strip()
    raise RuntimeError("สคริปต์ใช้ตัวเลขที่ไม่ได้มาจากตารางจำลอง: " + " | ".join(issues))


def mock_sim_story(topic: str) -> SimPlan:
    """Offline plan (no LLM) for render tests: a 10-day iced-tea stall with a price war."""
    days = [(25, 30, ""), (25, 42, ""), (25, 48, ""), (25, 20, "ร้านข้างๆ ขายแก้วละ 15"), (15, 55, "ลดราคาสู้"),
            (15, 60, ""), (15, 58, "ค่าน้ำแข็งขึ้น"), (25, 35, "กลับราคาเดิม"), (25, 44, ""), (25, 50, "")]
    sim = compute({"model": "shop", "product": "ชาเย็น", "unit": "แก้ว", "start_cost": 1500, "fixed_cost_per_day": 120,
                   "unit_cost": 12, "competitor_price": 15,
                   "days": [{"price": p, "units": u, "event": e} for p, u, e in days],
                   "assumptions": ["สมมติต้นทุนแก้วละ 12 บาท", "สมมติค่าน้ำแข็งและที่วันละ 120 บาท"]})
    s = sim.steps

    def b(shot, n, step, setting, emo, punch="", vs=("", "", "", "")):
        sc = _scene({"narration": n, "spoken": n, "shot": shot, "step": step, "setting": setting, "emotion": emo,
                     "punch": punch, "versus_left": vs[0], "versus_left_label": vs[1], "versus_right": vs[2],
                     "versus_right_label": vs[3]}, len(s) - 1)
        return sc
    scenes = [
        b("scene", "ถ้าเปิดร้านชาเย็นหน้าโรงเรียน 10 วัน จะได้กำไรเท่าไหร่?", 0, "school", "think", "10 วัน กำไรเท่าไหร่?"),
        b("scene", f"สมมติลงทุนรถเข็นกับอุปกรณ์ {fmt(1500)} บาท ขายแก้วละ 25 บาท", 0, "stall", "neutral", "ทุน ฿1,500"),
        b("scene", f"สามวันแรก ขายดีขึ้นเรื่อยๆ ขาดทุนเหลือแค่ {fmt(abs(s[3].value))} บาท", 3, "stall", "happy", "ขายดี!"),
        b("versus", "แต่วันที่ 4 ร้านข้างๆ ขายแก้วละ 15 บาท ลูกค้าหายไปครึ่งนึง", 4, "stall", "shock", "",
          ("฿25", "ร้านเรา", "฿15", "ร้านข้างๆ")),
        b("scene", "เราเลยลดเหลือ 15 บาท ขายได้เยอะขึ้น แต่กำไรต่อแก้วเหลือแค่ 3 บาท", 7, "stall", "worry", "กำไรแก้วละ 3"),
        b("chart", "พอกลับไปขายราคาเดิม กำไรก็ค่อยๆ กลับมา", 10, "stall", "think"),
        b("scene", f"ครบ 10 วัน กำไรสะสม {fmt(s[-1].value)} บาท", 10, "stall", "mindblown", f"฿{fmt(s[-1].value)}"),
        b("lesson", "สงครามราคา ไม่มีใครชนะ คุณจะสู้ราคา หรือสู้ด้วยรสชาติ คอมเมนต์บอกกันหน่อย", 10, "stall", "happy"),
    ]
    return SimPlan(topic=topic, title="เปิดร้านชาเย็น 10 วัน ได้กำไรเท่าไหร่?", scenes=scenes,
                   post_caption="ลองเปิดร้านชาเย็นหน้าโรงเรียน 10 วัน เจอร้านข้างๆ ตัดราคา\nคุณจะสู้ราคาไหม? คอมเมนต์บอกกันหน่อย 👇",
                   hashtags=["#เงินทองจำลอง", "#ค้าขาย", "#ชาเย็น"], sources=[],
                   hook_title="ร้านชาเย็น 10 วัน", hook_subtitle="กำไรเท่าไหร่?", style="sim", sim=sim,
                   lesson="สงครามราคา ไม่มีใครชนะ", assumptions=sim.assumptions)
