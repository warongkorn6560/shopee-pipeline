"""
"sim" style renderer (money theme): a flat cartoon setting drawn in code, the piggy-bank mascot acting
out each beat, a day/year counter, a running money counter that counts up to the computed value, price-war
"VS" cards, an animated chart of the whole run, and a lesson card. Every number drawn comes from the
simulation table (sim.py), never from the script. The soundtrack reuses the story mixer.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from ..config import FONT_DISPLAY_MEDIUM_PATH, FONT_DISPLAY_PATH, FONT_PATH, FPS, OUTPUT_DIR, VIDEO_H, VIDEO_W
from . import piggy
from .render import (
    CROSSFADE, _Writer, _ease, _mix, _punch_sprite, _scaled, _subtitle_chunks, _subtitle_sprite, _text_block,
)
from .sim import DISCLAIMER, fmt

W, H = VIDEO_W, VIDEO_H
GROUND_Y = 1500
INK = (34, 24, 30)
GREEN = (36, 170, 90)
RED = (222, 58, 58)
YELLOW = (255, 214, 64)
CREAM = (255, 248, 230)

SKY = {"stall": ((255, 214, 170), (255, 240, 214)), "school": ((150, 210, 255), (220, 240, 255)),
       "market": ((255, 196, 150), (255, 232, 200)), "home": ((190, 170, 255), (232, 222, 255)),
       "bank": ((160, 220, 210), (226, 246, 240)), "office": ((170, 200, 240), (228, 236, 250)),
       "street": ((140, 200, 255), (214, 236, 255))}


# ---------------------------------------------------------------------------
# Settings (backgrounds), drawn once per beat
# ---------------------------------------------------------------------------
def _gradient(top, bottom) -> Image.Image:
    col = np.linspace(np.array(top, float), np.array(bottom, float), H).astype(np.uint8)
    return Image.fromarray(np.repeat(col[:, None, :], W, axis=1), "RGB").convert("RGBA")


def _building(d, x, w, h, body, roof=None, windows=True):
    top = GROUND_Y - h
    d.rectangle((x, top, x + w, GROUND_Y), fill=body, outline=INK, width=5)
    if roof:
        d.polygon([(x - 20, top), (x + w / 2, top - 90), (x + w + 20, top)], fill=roof, outline=INK, width=5)
    if windows:
        for wy in range(top + 40, GROUND_Y - 120, 110):
            for wx in range(x + 30, x + w - 60, 90):
                d.rectangle((wx, wy, wx + 54, wy + 64), fill=(200, 230, 255), outline=INK, width=4)


def _awning(d, x0, x1, y, colors=((230, 60, 60), (255, 255, 255))):
    n = 8
    step = (x1 - x0) / n
    for k in range(n):
        d.rectangle((x0 + k * step, y, x0 + (k + 1) * step, y + 70), fill=colors[k % 2], outline=INK, width=4)
        d.chord((x0 + k * step, y + 40, x0 + (k + 1) * step, y + 100), 0, 180, fill=colors[k % 2], outline=INK, width=4)


def _sign(img, text, x, y, size=64, fill=YELLOW):
    t = _text_block(text, FONT_DISPLAY_PATH, size, INK + (255,), max_w=420, max_lines=1, min_size=30)
    if not t:
        return
    w, h = t.width + 50, t.height + 20
    s = Image.new("RGBA", (w, h))
    ImageDraw.Draw(s).rounded_rectangle((0, 0, w - 1, h - 1), radius=18, fill=fill + (255,), outline=INK + (255,), width=5)
    s.alpha_composite(t, (25, 8))
    img.alpha_composite(s, (int(x - w / 2), int(y)))


def background(setting: str, price: float = 0, product: str = "") -> Image.Image:
    img = _gradient(*SKY.get(setting, SKY["street"]))
    d = ImageDraw.Draw(img)
    d.ellipse((780, 160, 960, 340), fill=(255, 236, 140))                                # sun
    for cx, cy in ((180, 300), (620, 230)):                                              # clouds
        for dx, r in ((0, 50), (55, 65), (120, 48)):
            d.ellipse((cx + dx - r, cy - r, cx + dx + r, cy + r), fill=(255, 255, 255, 235))
    if setting == "school":
        _building(d, 60, 960, 560, (250, 236, 200), (200, 90, 70))
        d.rectangle((420, GROUND_Y - 260, 660, GROUND_Y), fill=(140, 90, 60), outline=INK, width=5)  # gate
        _sign(img, "โรงเรียน", 540, GROUND_Y - 560 - 40, 54, fill=(255, 255, 255))
    elif setting == "bank":
        _building(d, 120, 840, 600, (236, 236, 228), (120, 140, 160), windows=False)
        for cx in range(200, 900, 140):
            d.rectangle((cx, GROUND_Y - 520, cx + 50, GROUND_Y - 30), fill=(250, 250, 245), outline=INK, width=4)
        _sign(img, "ธนาคาร", 540, GROUND_Y - 600 - 30, 54, fill=(255, 255, 255))
    elif setting == "home":
        _building(d, 180, 720, 480, (255, 222, 180), (170, 80, 90))
        d.rectangle((470, GROUND_Y - 220, 610, GROUND_Y), fill=(150, 100, 70), outline=INK, width=5)
    elif setting == "office":
        _building(d, 40, 380, 900, (190, 205, 225))
        _building(d, 460, 300, 700, (170, 190, 215))
        _building(d, 800, 260, 820, (200, 214, 232))
    elif setting == "market":
        for k, x in enumerate((40, 390, 740)):
            d.rectangle((x, GROUND_Y - 300, x + 300, GROUND_Y), fill=(250, 240, 220), outline=INK, width=5)
            _awning(d, x - 10, x + 310, GROUND_Y - 380,
                    ((60, 160, 90), (255, 255, 255)) if k % 2 else ((240, 140, 40), (255, 255, 255)))
    else:                                                                               # street / stall
        _building(d, 0, 330, 640, (240, 214, 190))
        _building(d, 360, 360, 520, (220, 200, 230))
        _building(d, 750, 330, 700, (210, 228, 210))
    d.rectangle((0, GROUND_Y, W, H), fill=(200, 196, 188))                                # pavement
    d.line((0, GROUND_Y, W, GROUND_Y), fill=INK, width=6)
    if setting in ("stall", "school", "market"):                                        # our cart
        d.rectangle((560, GROUND_Y - 300, 1020, GROUND_Y - 60), fill=(255, 250, 240), outline=INK, width=6)
        _awning(d, 540, 1040, GROUND_Y - 470)
        d.line((570, GROUND_Y - 400, 570, GROUND_Y - 300), fill=INK, width=8)
        d.line((1010, GROUND_Y - 400, 1010, GROUND_Y - 300), fill=INK, width=8)
        for wx in (620, 960):
            d.ellipse((wx - 50, GROUND_Y - 100, wx + 50, GROUND_Y), fill=(80, 80, 90), outline=INK, width=6)
        for k in range(4):                                                              # cups on the counter
            x = 620 + k * 95
            d.polygon([(x, GROUND_Y - 380), (x + 56, GROUND_Y - 380), (x + 48, GROUND_Y - 300), (x + 8, GROUND_Y - 300)],
                      fill=(214, 150, 90), outline=INK, width=4)
        if price:
            _sign(img, f"{product} ฿{fmt(price)}".strip(), 790, GROUND_Y - 250, 60)
    return img


# ---------------------------------------------------------------------------
# HUD sprites
# ---------------------------------------------------------------------------
def _pill(text: str, size: int, fg, bg, font=FONT_DISPLAY_PATH, pad=(34, 14), radius=None) -> Image.Image:
    t = _text_block(text, font, size, fg + (255,), max_w=900, max_lines=1, min_size=24)
    w, h = t.width + pad[0] * 2, t.height + pad[1] * 2
    s = Image.new("RGBA", (w, h))
    ImageDraw.Draw(s).rounded_rectangle((0, 0, w - 1, h - 1), radius=radius or h // 2, fill=bg + (255,),
                                        outline=INK + (255,), width=5)
    s.alpha_composite(t, (pad[0], pad[1] - 4))
    return s


def _money_panel(label: str, value: float, delta: float | None, k_delta: float) -> Image.Image:
    panel = Image.new("RGBA", (W - 80, 250))
    d = ImageDraw.Draw(panel)
    d.rounded_rectangle((0, 0, panel.width - 1, 230), radius=36, fill=(255, 255, 255, 240), outline=INK + (255,), width=6)
    lab = _text_block(label, FONT_DISPLAY_MEDIUM_PATH, 46, (90, 80, 90, 255), max_w=600, max_lines=1)
    panel.alpha_composite(lab, (40, 18))
    col = GREEN if value >= 0 else RED
    txt = ("-" if value < 0 else "") + "฿" + fmt(round(abs(value)))
    num = _text_block(txt, FONT_DISPLAY_PATH, 112, col + (255,), max_w=panel.width - 80, max_lines=1, min_size=60)
    panel.alpha_composite(num, (36, 78))
    if delta is not None and abs(delta) > 0.004 and k_delta > 0:
        b = _pill(("+" if delta >= 0 else "-") + "฿" + fmt(round(abs(delta))), 48, (255, 255, 255),
                  GREEN if delta >= 0 else RED)
        b = _scaled(b, 0.6 + 0.4 * _ease(k_delta))
        panel.alpha_composite(b, (panel.width - b.width - 30, 24))
    return panel


def _vs_card(value: str, label: str, color) -> Image.Image:
    card = Image.new("RGBA", (440, 520))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle((0, 0, 439, 519), radius=40, fill=color + (255,), outline=INK + (255,), width=8)
    v = _text_block(value, FONT_DISPLAY_PATH, 150, (255, 255, 255, 255), max_w=400, max_lines=1, stroke=8, min_size=70)
    if v:
        card.alpha_composite(v, ((440 - v.width) // 2, 110))
    lb = _text_block(label, FONT_DISPLAY_MEDIUM_PATH, 56, (255, 255, 255, 255), max_w=400, max_lines=1, stroke=5)
    if lb:
        card.alpha_composite(lb, ((440 - lb.width) // 2, 360))
    return card


def _vs_burst() -> Image.Image:
    r = 120
    img = Image.new("RGBA", (r * 2 + 20, r * 2 + 20))
    d = ImageDraw.Draw(img)
    c = r + 10
    pts = [(c + (r if k % 2 == 0 else r * 0.7) * math.cos(k * math.pi / 10),
            c + (r if k % 2 == 0 else r * 0.7) * math.sin(k * math.pi / 10)) for k in range(20)]
    d.polygon(pts, fill=YELLOW + (255,), outline=INK + (255,), width=6)
    t = _text_block("VS", FONT_DISPLAY_PATH, 96, RED + (255,), max_w=200, max_lines=1, stroke=4)
    img.alpha_composite(t, (c - t.width // 2, c - t.height // 2 - 6))
    return img


def _chart(sim, upto: int, reveal: float) -> Image.Image:
    cw, ch = W - 120, 760
    img = Image.new("RGBA", (cw, ch))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, cw - 1, ch - 1), radius=36, fill=(255, 255, 255, 245), outline=INK + (255,), width=6)
    series = [[s.value for s in sim.steps]]
    if sim.steps[0].second is not None:
        series.append([s.second or 0 for s in sim.steps])
    lo = min(min(sr) for sr in series + [[0]])
    hi = max(max(sr) for sr in series + [[1]])
    x0, x1, y0, y1 = 70, cw - 50, ch - 90, 60
    px = lambda k: x0 + (x1 - x0) * k / max(len(sim.steps) - 1, 1)       # noqa: E731
    py = lambda v: y0 - (y0 - y1) * (v - lo) / max(hi - lo, 1e-9)        # noqa: E731
    d.line((x0, py(0), x1, py(0)), fill=(170, 170, 170, 255), width=3)
    n = upto + reveal if upto < len(sim.steps) - 1 else upto
    for si, sr in enumerate(series[::-1]):
        col = (150, 150, 160) if (si == 0 and len(series) > 1) else GREEN
        pts = []
        for k in range(int(math.floor(n)) + 1):
            pts.append((px(k), py(sr[k])))
        frac = n - math.floor(n)
        if frac and int(n) + 1 < len(sr):
            k = int(n)
            pts.append((px(k + frac), py(sr[k] + (sr[k + 1] - sr[k]) * frac)))
        if len(pts) > 1:
            d.line(pts, fill=col + (255,), width=12, joint="curve")
        if pts:
            d.ellipse((pts[-1][0] - 14, pts[-1][1] - 14, pts[-1][0] + 14, pts[-1][1] + 14), fill=col + (255,), outline=INK + (255,), width=4)
    for k in (0, len(sim.steps) - 1):
        t = _text_block(sim.steps[k].label, FONT_DISPLAY_MEDIUM_PATH, 34, (90, 80, 90, 255), max_w=300, max_lines=1)
        img.alpha_composite(t, (int(min(max(px(k) - t.width / 2, 20), cw - t.width - 20)), ch - 70))
    if len(series) > 1:
        lg = _text_block(f"เขียว = {sim.counter_label} · เทา = {sim.second_label}", FONT_DISPLAY_MEDIUM_PATH, 32,
                         (90, 80, 90, 255), max_w=cw - 80, max_lines=1)
        img.alpha_composite(lg, (40, 14))
    return img


def _lesson_card(text: str) -> Image.Image:
    t = _text_block(text, FONT_DISPLAY_PATH, 92, INK + (255,), max_w=820, max_lines=3, align="center", min_size=54)
    w, h = max(t.width + 120, 700), t.height + 200
    card = Image.new("RGBA", (w, h))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle((10, 30, w - 10, h - 10), radius=30, fill=CREAM + (255,), outline=INK + (255,), width=7)
    head = _pill("บทเรียน", 46, (255, 255, 255), RED)
    card.alpha_composite(head, ((w - head.width) // 2, 0))
    card.alpha_composite(t, ((w - t.width) // 2, 120))
    return card.rotate(-2, resample=Image.BICUBIC, expand=True)


# ---------------------------------------------------------------------------
def render(plan, beat_durs: list[float], voice: Path, run_dir: Path, out_name: str) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    sim = plan.sim
    steps = sim.steps
    total_steps = len(steps) - 1
    silent = run_dir / "story_silent.mp4"
    writer = _Writer(silent, sum(beat_durs))
    sim_chip = _pill("สถานการณ์จำลอง", 40, INK, YELLOW)
    footer = _text_block(DISCLAIMER, FONT_PATH, 28, (255, 255, 255, 200), max_w=1000, max_lines=1, min_size=18)
    mascots = {e: piggy.load(e) for e in piggy.EMOTIONS}
    shade = Image.new("RGBA", (W, H))
    ImageDraw.Draw(shade).rectangle((0, 1540, W, H), fill=(0, 0, 0, 150))
    coin = piggy.coin(38)
    bg_cache: dict = {}
    pops: list[float] = []
    prev_value, prev_kind, t0 = steps[0].value, None, 0.0

    for i, (sc, d) in enumerate(zip(plan.scenes, beat_durs)):
        n = max(int(round(d * FPS)), 1)
        step = steps[min(getattr(sc, "step", 0), total_steps)]
        k_step = min(getattr(sc, "step", 0), total_steps)
        shot = sc.visual
        key = (sc.place, step.price if sim.model == "shop" and k_step else 0)
        if key not in bg_cache:
            bg_cache[key] = background(sc.place, key[1], sim.params.get("product", "") if key[1] else "")
        bg = bg_cache[key]
        chunks = _subtitle_chunks(sc.narration)
        bounds = np.cumsum([max(len(c), 1) for c in chunks]) / sum(max(len(c), 1) for c in chunks) * n
        subs = [_subtitle_sprite(c) for c in chunks]
        punch = _punch_sprite(sc.punch) if sc.punch else None
        day_chip = _pill(f"{step.label} / {total_steps}" if k_step and sim.model != "savings" else
                         (step.label if k_step else steps[0].label), 56, (255, 255, 255), INK, radius=24)
        if i == 0 and (plan.hook_title or plan.hook_subtitle):
            punch = _punch_sprite(plan.hook_title) if plan.hook_title else punch
        vs = getattr(sc, "versus", ("", "", "", ""))
        vs_cards = (_vs_card(vs[0], vs[1], RED), _vs_card(vs[2], vs[3], (60, 120, 220))) if shot == "versus" and vs[0] and vs[2] else None
        lesson = _lesson_card(plan.lesson or sc.narration) if shot == "lesson" else None
        mascot = mascots.get(sc.emotion, mascots["neutral"])
        count_n = max(int(n * 0.45), 1)
        delta = step.value - prev_value
        if abs(delta) > 0.004:
            pops.append(t0 + count_n / FPS)
        print(f"    [render] beat {i + 1}/{len(plan.scenes)} {shot} {step.label} {d:.1f}s")

        for f in range(n):
            t = f / max(n - 1, 1)
            z = 1.0 + 0.04 * _ease(t)
            w2, h2 = W / z, H / z
            frame = bg.transform((W, H), Image.EXTENT, ((W - w2) / 2, (H - h2) / 2 + 20, (W + w2) / 2, (H + h2) / 2 + 20),
                                 Image.BILINEAR).convert("RGBA")
            kc = _ease(f / count_n)
            value = prev_value + delta * kc
            frame.alpha_composite(sim_chip, (40, 70))
            frame.alpha_composite(day_chip, (W - 40 - day_chip.width, 60))
            frame.alpha_composite(_money_panel(sim.counter_label, value, delta if f >= count_n else None,
                                               (f - count_n) / 6), (40, 190))

            if shot == "chart":
                frame.alpha_composite(_chart(sim, max(k_step - 1, 0) if k_step else 0, _ease(t * 1.4)), (60, 480))
                m = _scaled(mascot, 0.42)
                frame.alpha_composite(m, (W - m.width - 30, GROUND_Y - m.height + 60))
            elif vs_cards:
                k1 = _ease(f / 8)
                frame.alpha_composite(vs_cards[0], (int(50 - (1 - k1) * 600), 600))
                k2 = _ease((f - 4) / 8)
                frame.alpha_composite(vs_cards[1], (int(W - 490 + (1 - k2) * 600), 640))
                if f >= 10:
                    b = _vs_burst()
                    kb = min((f - 10) / 6, 1)
                    b = _scaled(b, 1.6 - 0.6 * _ease(kb)) if kb < 1 else b
                    frame.alpha_composite(b, ((W - b.width) // 2, 880 - b.height // 2))
                m = _scaled(mascot, 0.38)
                frame.alpha_composite(m, ((W - m.width) // 2, GROUND_Y - m.height + 140))
            elif lesson is not None:
                kl = _ease(f / 9)
                ls = _scaled(lesson, 0.7 + 0.3 * kl) if kl < 1 else lesson
                frame.alpha_composite(ls, ((W - ls.width) // 2, 600))
                m = _scaled(mascot, 0.5)
                frame.alpha_composite(m, ((W - m.width) // 2, GROUND_Y - m.height + 150))
            else:
                pop = 0.75 + 0.25 * _ease(f / 7)
                bob = int(10 * math.sin(f / 7))
                m = _scaled(mascot, 0.9 * pop)
                frame.alpha_composite(m, (110 - int((m.width - mascot.width * 0.9) / 2), GROUND_Y - m.height + 70 + bob))
                if delta > 0.004 and count_n - 10 <= f <= count_n:          # the running gag: a coin drops in
                    kk = (f - (count_n - 10)) / 10
                    frame.alpha_composite(coin, (110 + int(mascot.width * 0.45) - coin.width // 2,
                                                 int(GROUND_Y - mascot.width * 0.75 - 260 + 260 * kk * kk)))
                if punch is not None and f >= 3:
                    kp = min((f - 3) / 6, 1)
                    ps = _scaled(punch, 1.25 - 0.25 * _ease(kp)) if kp < 1 else punch
                    frame.alpha_composite(ps, ((W - ps.width) // 2, 500))
                if step.event and sim.model == "shop" and i:
                    ev = _pill(step.event, 40, INK, CREAM, font=FONT_DISPLAY_MEDIUM_PATH, radius=20)
                    frame.alpha_composite(ev, ((W - ev.width) // 2, 520 if punch is None else 760))

            frame.alpha_composite(shade)                                         # subtitle shade
            sub = subs[min(int(np.searchsorted(bounds, f, side="right")), len(subs) - 1)]
            if sub is not None:
                frame.alpha_composite(sub, ((W - sub.width) // 2, 1600))
            if footer is not None:
                frame.alpha_composite(footer, ((W - footer.width) // 2, H - 80))
            if prev_kind is not None and f < CROSSFADE and writer.last is not None and prev_kind != shot:
                frame = Image.blend(writer.last.convert("RGBA"), frame, (f + 1) / CROSSFADE)
            writer.write(frame)
        prev_value, prev_kind = step.value, shot
        t0 += d

    writer.close()
    return _mix(silent, voice, beat_durs, OUTPUT_DIR / out_name, run_dir, pops)
