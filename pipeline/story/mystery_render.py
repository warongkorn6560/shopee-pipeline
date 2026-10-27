"""
"mystery" style renderer: a dark noir look built from silhouettes and light rather than cartoon
drawing — a layered night setting (rain, fog, a lamp or window glow, film grain, slow push-in), suspects
as backlit silhouettes with name plates, evidence tags for numbered clues, a countdown pause card, and a
reveal that strings the clues back to the answer. A small owl silhouette with glowing eyes is the
recurring narrator. Everything is drawn in code.
"""

from __future__ import annotations

import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from ..config import FONT_DISPLAY_MEDIUM_PATH, FONT_DISPLAY_PATH, FONT_PATH, FPS, OUTPUT_DIR, VIDEO_H, VIDEO_W
from .mystery import FICTION
from .render import CROSSFADE, _Writer, _ease, _mix, _scaled, _subtitle_chunks, _subtitle_sprite, _text_block

W, H = VIDEO_W, VIDEO_H
AMBER = (255, 184, 92)
RED = (214, 40, 48)
PAPER = (226, 208, 170)
INK = (24, 20, 18)
HORIZON = 1380

TINT = {"street": (18, 26, 46), "apartment": (24, 22, 40), "mansion": (30, 22, 30), "office": (16, 28, 40),
        "train": (20, 26, 34), "cafe": (34, 24, 20), "school": (18, 30, 34), "forest": (12, 26, 22)}


# ---------------------------------------------------------------------------
# Setting
# ---------------------------------------------------------------------------
def _sky(tint) -> Image.Image:
    top = np.array([max(c - 14, 0) for c in tint], float)
    bot = np.array([min(c + 26, 255) for c in tint], float)
    col = np.linspace(top, bot, H).astype(np.uint8)
    return Image.fromarray(np.repeat(col[:, None, :], W, axis=1), "RGB").convert("RGBA")


def _skyline(d, rng, base, h_lo, h_hi, color, lit, x_step=(90, 200)):
    x = -40
    while x < W + 40:
        w = rng.randint(*x_step)
        h = rng.randint(h_lo, h_hi)
        d.rectangle((x, base - h, x + w, base), fill=color)
        if lit:
            for wy in range(base - h + 30, base - 40, 46):
                for wx in range(x + 14, x + w - 24, 34):
                    if rng.random() < lit:
                        d.rectangle((wx, wy, wx + 16, wy + 24), fill=AMBER + (rng.randint(120, 230),))
        x += w + rng.randint(0, 20)


def background(setting: str, seed: int = 7) -> Image.Image:
    rng = random.Random(seed)
    tint = TINT.get(setting, TINT["street"])
    img = _sky(tint)
    glow = Image.new("RGBA", (W, H))
    g = ImageDraw.Draw(glow)
    g.ellipse((640, 170, 900, 430), fill=(230, 230, 210, 255))                   # moon
    glow = glow.filter(ImageFilter.GaussianBlur(40))
    img.alpha_composite(glow)
    d = ImageDraw.Draw(img)
    d.ellipse((690, 220, 850, 380), fill=(236, 232, 214, 255))
    far = tuple(min(c + 12, 255) for c in tint) + (255,)
    near = tuple(max(c - 10, 0) for c in tint) + (255,)
    if setting == "forest":
        for k in range(26):
            x = rng.randint(-60, W + 60)
            h = rng.randint(500, 1100)
            col = far if k < 13 else near
            d.polygon([(x, HORIZON - h), (x - 120, HORIZON), (x + 120, HORIZON)], fill=col)
    else:
        _skyline(d, rng, HORIZON - 120, 420, 900, far, 0.12)
        _skyline(d, rng, HORIZON, 300, 760, near, 0.07 if setting != "office" else 0.2, (140, 320))
    if setting in ("mansion", "apartment", "school"):                            # the lit window of the scene
        d.rectangle((140, 760, 520, HORIZON), fill=(10, 8, 10, 255))
        d.rectangle((210, 860, 450, 1120), fill=AMBER + (255,))
        d.line((330, 860, 330, 1120), fill=(10, 8, 10, 255), width=10)
        d.line((210, 990, 450, 990), fill=(10, 8, 10, 255), width=10)
    d.rectangle((0, HORIZON, W, H), fill=(8, 8, 12, 255))                       # wet ground
    lamp = Image.new("RGBA", (W, H))
    lg = ImageDraw.Draw(lamp)
    lg.polygon([(860, 880), (600, HORIZON + 260), (1120, HORIZON + 260)], fill=AMBER + (70,))
    lg.ellipse((700, HORIZON + 140, 1040, HORIZON + 300), fill=AMBER + (90,))
    lamp = lamp.filter(ImageFilter.GaussianBlur(30))
    img.alpha_composite(lamp)
    d = ImageDraw.Draw(img)
    d.line((860, 880, 860, HORIZON + 200), fill=(6, 6, 8, 255), width=14)       # street lamp
    d.rectangle((830, 860, 890, 890), fill=(6, 6, 8, 255))
    d.ellipse((842, 884, 878, 910), fill=AMBER + (255,))
    fog = Image.new("RGBA", (W, H))
    fg = ImageDraw.Draw(fog)
    for y in range(HORIZON - 260, HORIZON + 120, 4):
        fg.line((0, y, W, y), fill=(200, 210, 230, int(38 * (1 - abs(y - HORIZON + 70) / 200) if abs(y - HORIZON + 70) < 200 else 0)))
    img.alpha_composite(fog)
    return img


def _vignette() -> Image.Image:
    yy, xx = np.mgrid[0:H, 0:W]
    r = np.sqrt(((xx - W / 2) / (W * 0.62)) ** 2 + ((yy - H * 0.45) / (H * 0.6)) ** 2)
    a = (np.clip(r - 0.55, 0, 1) * 330).clip(0, 235).astype(np.uint8)
    v = np.zeros((H, W, 4), np.uint8)
    v[..., 3] = a
    return Image.fromarray(v, "RGBA")


def _rain(seed: int) -> list[Image.Image]:
    rng = random.Random(seed)
    drops = [(rng.uniform(0, W), rng.uniform(0, H), rng.uniform(30, 70), rng.uniform(26, 40)) for _ in range(170)]
    frames = []
    for k in range(12):
        img = Image.new("RGBA", (W, H))
        d = ImageDraw.Draw(img)
        for x, y, ln, sp in drops:
            yy = (y + k * sp) % H
            d.line((x, yy, x - ln * 0.18, yy + ln), fill=(190, 200, 230, 70), width=2)
        frames.append(img)
    return frames


def _grain(seed: int) -> Image.Image:
    rng = np.random.default_rng(seed)
    n = rng.integers(0, 255, (H // 3, W // 3), dtype=np.uint8)
    a = np.zeros((H // 3, W // 3, 4), np.uint8)
    a[..., :3] = n[..., None]
    a[..., 3] = 16
    return Image.fromarray(a, "RGBA").resize((W, H), Image.NEAREST)


# ---------------------------------------------------------------------------
# Sprites
# ---------------------------------------------------------------------------
def _pill(text: str, size: int, fg, bg, font=FONT_DISPLAY_MEDIUM_PATH, outline=None) -> Image.Image:
    t = _text_block(text, font, size, fg + (255,), max_w=900, max_lines=1, min_size=22)
    w, h = t.width + 52, t.height + 22
    s = Image.new("RGBA", (w, h))
    ImageDraw.Draw(s).rounded_rectangle((0, 0, w - 1, h - 1), radius=12, fill=bg, outline=outline, width=3 if outline else 0)
    s.alpha_composite(t, (26, 8))
    return s


def _figure(color=(6, 6, 8, 255), scale=1.0) -> Image.Image:
    """A standing silhouette (head, shoulders, coat) — no faces, so it reads as noir, not clip art."""
    w, h = int(300 * scale), int(620 * scale)
    img = Image.new("RGBA", (w * 4, h * 4))
    d = ImageDraw.Draw(img)
    s = 4 * scale
    d.ellipse((105 * s, 20 * s, 195 * s, 120 * s), fill=color)                  # head
    d.polygon([(150 * s, 120 * s), (40 * s, 190 * s), (20 * s, 620 * s), (280 * s, 620 * s), (260 * s, 190 * s)], fill=color)
    d.rounded_rectangle((30 * s, 170 * s, 270 * s, 260 * s), radius=int(50 * s), fill=color)
    return img.resize((w, h), Image.LANCZOS)


def _rim(sil: Image.Image, color=AMBER) -> Image.Image:
    """Back-light: a soft coloured edge around a silhouette."""
    a = sil.split()[3]
    edge = Image.new("RGBA", sil.size, color + (0,))
    edge.putalpha(a.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(6)))
    out = Image.new("RGBA", sil.size)
    out.alpha_composite(edge)
    out.alpha_composite(sil)
    return out


def _owl(emotion: str) -> Image.Image:
    """The narrator: an owl silhouette in a detective hat; only the glowing eyes change."""
    S = 4
    img = Image.new("RGBA", (220 * S, 260 * S))
    d = ImageDraw.Draw(img)
    body = (8, 8, 10, 255)
    d.ellipse((30 * S, 70 * S, 190 * S, 250 * S), fill=body)
    d.polygon([(40 * S, 100 * S), (55 * S, 40 * S), (85 * S, 85 * S)], fill=body)          # ear tufts
    d.polygon([(180 * S, 100 * S), (165 * S, 40 * S), (135 * S, 85 * S)], fill=body)
    d.ellipse((50 * S, 52 * S, 170 * S, 84 * S), fill=body)                                   # hat brim
    d.rounded_rectangle((72 * S, 18 * S, 148 * S, 70 * S), radius=18 * S, fill=body)
    eye = (255, 196, 70, 255)
    for cx in (82, 138):
        if emotion == "happy":
            d.arc(((cx - 20) * S, 112 * S, (cx + 20) * S, 146 * S), 200, 340, fill=eye, width=7 * S)
        elif emotion in ("shock", "mindblown"):
            d.ellipse(((cx - 24) * S, 104 * S, (cx + 24) * S, 152 * S), fill=eye)
            d.ellipse(((cx - 7) * S, 121 * S, (cx + 7) * S, 135 * S), fill=body)
        elif emotion in ("think", "worry"):
            d.chord(((cx - 20) * S, 108 * S, (cx + 20) * S, 148 * S), 0, 180, fill=eye)
            d.ellipse(((cx - 5) * S, 126 * S, (cx + 5) * S, 136 * S), fill=body)
        else:
            d.ellipse(((cx - 20) * S, 108 * S, (cx + 20) * S, 148 * S), fill=eye)
            d.ellipse(((cx - 6) * S, 122 * S, (cx + 6) * S, 134 * S), fill=body)
    d.polygon([(110 * S, 150 * S), (100 * S, 166 * S), (120 * S, 166 * S)], fill=(255, 196, 70, 200))
    img = img.resize((220, 260), Image.LANCZOS)
    return _rim(img, (120, 140, 200))


def _icon(kind: str, size: int = 150) -> Image.Image:
    """White line-art evidence icons."""
    S = 4
    img = Image.new("RGBA", (size * S, size * S))
    d = ImageDraw.Draw(img)
    c, lw, k = (245, 240, 230, 255), 9 * S, size * S / 150
    p = lambda *v: [x * k for x in v]   # noqa: E731
    if kind == "key":
        d.ellipse(p(20, 50, 70, 100), outline=c, width=lw); d.line(p(70, 75, 130, 75), fill=c, width=lw)
        d.line(p(110, 75, 110, 95), fill=c, width=lw); d.line(p(125, 75, 125, 92), fill=c, width=lw)
    elif kind == "clock":
        d.ellipse(p(25, 25, 125, 125), outline=c, width=lw); d.line(p(75, 75, 75, 42), fill=c, width=lw)
        d.line(p(75, 75, 100, 88), fill=c, width=lw)
    elif kind == "footprint":
        d.ellipse(p(45, 40, 95, 110), outline=c, width=lw); d.ellipse(p(55, 112, 90, 140), outline=c, width=lw)
        for x, y in ((48, 22), (64, 14), (80, 14), (94, 22)):
            d.ellipse(p(x - 7, y - 7, x + 7, y + 7), fill=c)
    elif kind == "cup":
        d.polygon(p(35, 50, 105, 50, 95, 125, 45, 125), outline=c, width=lw); d.arc(p(90, 60, 130, 100), 270, 90, fill=c, width=lw)
        for x in (55, 72, 89):
            d.arc(p(x - 8, 15, x + 8, 45), 90, 270, fill=c, width=5 * S)
    elif kind == "phone":
        d.rounded_rectangle(p(45, 15, 105, 135), radius=int(12 * k), outline=c, width=lw); d.line(p(65, 120, 85, 120), fill=c, width=lw)
    elif kind == "letter":
        d.rectangle(p(20, 40, 130, 115), outline=c, width=lw); d.line(p(20, 40, 75, 85, 130, 40), fill=c, width=lw)
    elif kind == "umbrella":
        d.chord(p(20, 25, 130, 115), 180, 360, outline=c, width=lw); d.line(p(75, 70, 75, 125), fill=c, width=lw)
        d.arc(p(55, 110, 75, 135), 0, 180, fill=c, width=lw)
    elif kind == "ring":
        d.ellipse(p(35, 55, 115, 135), outline=c, width=lw); d.polygon(p(60, 55, 75, 25, 90, 55), outline=c, width=lw)
    elif kind == "door":
        d.rectangle(p(40, 15, 110, 135), outline=c, width=lw); d.ellipse(p(88, 72, 100, 84), fill=c)
    elif kind == "light":
        d.ellipse(p(40, 15, 110, 85), outline=c, width=lw); d.rectangle(p(58, 85, 92, 115), outline=c, width=lw)
    elif kind == "car":
        d.rounded_rectangle(p(15, 70, 135, 110), radius=int(10 * k), outline=c, width=lw)
        d.polygon(p(40, 70, 55, 42, 100, 42, 115, 70), outline=c, width=lw)
        for x in (45, 105):
            d.ellipse(p(x - 14, 98, x + 14, 126), fill=(0, 0, 0, 255), outline=c, width=lw)
    else:                                                                                   # photo
        d.rectangle(p(20, 30, 130, 120), outline=c, width=lw); d.polygon(p(30, 110, 65, 70, 90, 95, 105, 80, 122, 110), outline=c, width=lw)
    return img.resize((size, size), Image.LANCZOS)


def _evidence_tag(number: int, text: str, icon: str, *, small: bool = False) -> Image.Image:
    """A brown evidence tag with a string hole, the clue number and the clue."""
    k = 0.42 if small else 1.0
    w, h = 820, 360
    tag = Image.new("RGBA", (w, h))
    d = ImageDraw.Draw(tag)
    d.polygon([(70, 0), (w, 0), (w, h), (70, h), (0, h - 70), (0, 70)], fill=PAPER + (255,))
    d.ellipse((30, h // 2 - 22, 74, h // 2 + 22), fill=(40, 34, 28, 255))
    d.rectangle((110, 26, 300, 334), fill=(32, 28, 26, 255))
    tag.alpha_composite(_icon(icon, 150), (130, 105))
    head = _text_block(f"หลักฐาน #{number}", FONT_DISPLAY_PATH, 54, RED + (255,), max_w=480, max_lines=1)
    tag.alpha_composite(head, (330, 40))
    body = _text_block(text, FONT_DISPLAY_MEDIUM_PATH, 58, INK + (255,), max_w=460, max_lines=3, min_size=34)
    if body:
        tag.alpha_composite(body, (330, 130))
    noise = _grain(number).resize((w, h)).crop((0, 0, w, h))
    tag.alpha_composite(Image.composite(noise, Image.new("RGBA", (w, h)), tag.split()[3]))
    tag = tag.rotate(-3 if number % 2 else 2, resample=Image.BICUBIC, expand=True)
    return _scaled(tag, k) if small else tag


def _name_plate(name: str, role: str, hot: bool) -> Image.Image:
    n = _text_block(name, FONT_DISPLAY_PATH, 46, (255, 255, 255, 255), max_w=300, max_lines=1, min_size=26)
    r = _text_block(role, FONT_DISPLAY_MEDIUM_PATH, 32, (200, 196, 188, 255), max_w=300, max_lines=1, min_size=20)
    w = max(n.width if n else 0, r.width if r else 0) + 36
    h = (n.height if n else 0) + (r.height if r else 0) + 18
    img = Image.new("RGBA", (w, h))
    ImageDraw.Draw(img).rectangle((0, 0, w - 1, h - 1), fill=(RED if hot else (20, 20, 24)) + (235,))
    if n:
        img.alpha_composite(n, ((w - n.width) // 2, 4))
    if r:
        img.alpha_composite(r, ((w - r.width) // 2, 8 + (n.height if n else 0)))
    return img


def _punch(text: str) -> Image.Image | None:
    t = _text_block(text, FONT_DISPLAY_PATH, 110, (255, 255, 255, 255), max_w=960, max_lines=2, stroke=8,
                    align="center", min_size=60)
    if not t:
        return None
    glow = Image.new("RGBA", t.size, RED + (0,))
    glow.putalpha(t.split()[3].filter(ImageFilter.GaussianBlur(14)))
    out = Image.new("RGBA", t.size)
    out.alpha_composite(glow)
    out.alpha_composite(t)
    return out


# ---------------------------------------------------------------------------
def render(plan, beat_durs: list[float], voice: Path, run_dir: Path, out_name: str) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    silent = run_dir / "story_silent.mp4"
    writer = _Writer(silent, sum(beat_durs))
    bg = background(plan.setting, seed=len(plan.title))
    dark = Image.blend(bg, Image.new("RGBA", bg.size, (0, 0, 0, 255)), 0.55)
    rain = _rain(3)
    grain = [_grain(k) for k in range(4)]
    vign = _vignette()
    fiction = _pill("เรื่องแต่ง", 36, (255, 255, 255), (0, 0, 0, 170), outline=(255, 255, 255, 120))
    footer = _text_block(FICTION, FONT_PATH, 26, (220, 220, 220, 170), max_w=1000, max_lines=1, min_size=18)
    owls = {}
    suspects = plan.suspects or [{"name": "?", "role": ""}]
    sil = [_figure(scale=0.9 if len(suspects) > 3 else 1.0) for _ in suspects]
    total_clues = max([s.clue for s in plan.scenes if s.visual == "clue"] or [0])
    shown: dict[int, tuple[str, str]] = {}
    pops: list[float] = []
    prev_shot, t0 = None, 0.0

    for i, (sc, d) in enumerate(zip(plan.scenes, beat_durs)):
        n = max(int(round(d * FPS)), 1)
        shot = sc.visual
        chunks = _subtitle_chunks(sc.narration)
        bounds = np.cumsum([max(len(c), 1) for c in chunks]) / sum(max(len(c), 1) for c in chunks) * n
        subs = [_subtitle_sprite(c) for c in chunks]
        punch = _punch(plan.hook_title if i == 0 and plan.hook_title else sc.punch) if (sc.punch or i == 0) else None
        owl = owls.setdefault(sc.emotion, _owl(sc.emotion))
        if shot == "clue" and sc.clue:
            shown[sc.clue] = (sc.card_title, sc.icon)
            pops.append(t0 + 0.25)
        tag = _evidence_tag(sc.clue, *shown[sc.clue]) if shot == "clue" and sc.clue in shown else None
        small_tags = {k: _evidence_tag(k, *v, small=True) for k, v in sorted(shown.items())}
        counter = _pill(f"หลักฐาน {len(shown)}/{total_clues}", 38, AMBER, (0, 0, 0, 170)) if total_clues else None
        if shot == "pause":
            pops += [t0 + max(d - 3.2, 0.5) + k for k in range(3)]
        plates = [_name_plate(s["name"], s["role"], shot in ("reveal", "ending") and k == plan.answer_suspect)
                  for k, s in enumerate(suspects)]
        print(f"    [render] beat {i + 1}/{len(plan.scenes)} {shot} {d:.1f}s")

        for f in range(n):
            t = (t0 + f / FPS) / max(sum(beat_durs), 1)
            z = 1.0 + 0.10 * t                                      # one slow push-in across the episode
            w2, h2 = W / z, H / z
            base = dark if shot in ("pause", "reveal") else bg
            frame = base.transform((W, H), Image.EXTENT, ((W - w2) / 2, (H - h2) / 2, (W + w2) / 2, (H + h2) / 2),
                                   Image.BILINEAR)
            if shot != "pause":
                frame.alpha_composite(rain[f % len(rain)])

            if shot in ("suspects", "reveal", "ending"):
                gap = W / (len(suspects) + 1)
                for k, s in enumerate(sil):
                    hot = (shot != "suspects" and k == plan.answer_suspect) or (shot == "suspects" and sc.focus == k)
                    appear = _ease((f - k * 5) / 8) if shot == "suspects" else 1.0
                    if appear <= 0:
                        continue
                    fig = _rim(s, RED if hot and shot != "suspects" else AMBER) if hot or shot == "suspects" else s
                    if shot != "suspects" and not hot:
                        fig = Image.blend(Image.new("RGBA", fig.size), fig, 0.45)
                    x = int(gap * (k + 1) - fig.width / 2)
                    y = int(HORIZON - fig.height + 60 + (1 - appear) * 80)
                    if hot:
                        spot = Image.new("RGBA", (W, H))
                        ImageDraw.Draw(spot).polygon([(x + fig.width / 2 - 40, 380), (x - 60, HORIZON + 80),
                                                      (x + fig.width + 60, HORIZON + 80), (x + fig.width / 2 + 40, 380)],
                                                     fill=(255, 230, 190, 46))
                        frame.alpha_composite(spot.filter(ImageFilter.GaussianBlur(18)))
                    frame.alpha_composite(fig, (x, y))
                    pl = plates[k]
                    frame.alpha_composite(pl, (int(gap * (k + 1) - pl.width / 2), HORIZON + 80))
            elif shot == "scene" and sc.focus >= 0 and sc.focus < len(sil):
                fig = _rim(sil[sc.focus])
                frame.alpha_composite(fig, (W // 2 - fig.width // 2 + 120, HORIZON - fig.height + 60))

            if tag is not None:                                          # evidence tag slides in, then holds
                kt = _ease(f / 9)
                ts = _scaled(tag, 1.15 - 0.15 * kt) if kt < 1 else tag
                frame.alpha_composite(ts, (int((W - ts.width) / 2 + (1 - kt) * 500), 660))
            if shot == "reveal" and small_tags:                          # the clues, strung back to the answer
                ys = 150
                hot_x = W / (len(suspects) + 1) * (plan.answer_suspect + 1) if plan.answer_suspect >= 0 else W / 2
                dd = ImageDraw.Draw(frame)
                for k, st in small_tags.items():
                    x = 40 + (k - 1) * 340
                    lit = sc.clue == k
                    frame.alpha_composite(st if lit else Image.blend(Image.new("RGBA", st.size), st, 0.55), (x, ys))
                    if lit:
                        reach = _ease(f / 12)
                        sx, sy = x + st.width / 2, ys + st.height
                        dd.line((sx, sy, sx + (hot_x - sx) * reach, sy + (HORIZON - 640 - sy) * reach), fill=RED + (255,), width=6)
            if shot == "pause":
                card = _text_block("หยุดดู! ทายก่อน", FONT_DISPLAY_PATH, 130, (255, 255, 255, 255), max_w=980,
                                   max_lines=2, align="center")
                frame.alpha_composite(card, ((W - card.width) // 2, 520))
                left = d - f / FPS
                num = str(max(1, min(3, math.ceil(left)))) if left <= 3.2 else "?"
                nk = 1 - (left % 1) if left <= 3.2 else 0
                big = _text_block(num, FONT_DISPLAY_PATH, 330, RED + (255,), max_w=600, max_lines=1)
                big = _scaled(big, 1.25 - 0.25 * _ease(nk * 3))
                frame.alpha_composite(big, ((W - big.width) // 2, 820))
                ask = _text_block("คอมเมนต์คำตอบไว้ 👇".replace(" 👇", ""), FONT_DISPLAY_MEDIUM_PATH, 64, AMBER + (255,),
                                  max_w=900, max_lines=1, align="center")
                frame.alpha_composite(ask, ((W - ask.width) // 2, 1250))
            if punch is not None and shot not in ("pause",) and f >= 2:
                kp = min((f - 2) / 6, 1)
                ps = _scaled(punch, 1.3 - 0.3 * _ease(kp)) if kp < 1 else punch
                frame.alpha_composite(ps, ((W - ps.width) // 2, 400 if tag is None else 380))

            frame.alpha_composite(vign)
            frame.alpha_composite(grain[f % 4])
            if shot in ("scene", "clue"):                          # suspects/reveal need the whole stage
                bob = int(5 * math.sin(f / 10))
                frame.alpha_composite(owl, (34, HORIZON - 120 + bob))
            frame.alpha_composite(fiction, (40, 70))
            if counter is not None and shot not in ("pause",):
                frame.alpha_composite(counter, (W - 40 - counter.width, 70))
            sub = subs[min(int(np.searchsorted(bounds, f, side="right")), len(subs) - 1)]
            if sub is not None:
                frame.alpha_composite(sub, ((W - sub.width) // 2, 1600))
            if footer is not None:
                frame.alpha_composite(footer, ((W - footer.width) // 2, H - 76))
            if prev_shot is not None and prev_shot != shot and f < CROSSFADE and writer.last is not None:
                frame = Image.blend(writer.last.convert("RGBA"), frame, (f + 1) / CROSSFADE)
            writer.write(frame)
        prev_shot = shot
        t0 += d

    writer.close()
    return _mix(silent, voice, beat_durs, OUTPUT_DIR / out_name, run_dir, pops)
