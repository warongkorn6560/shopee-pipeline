"""
"doodle" renderer: hand-drawn doodle characters (doodle_cast.py) over real photos of ordinary places
that are stylised into a cool blue-grey cel look. Quiet motion like a hand-made reel — slow Ken Burns on
the background, a soft bob, characters sliding in, boiling lines, little shock/anger marks, rain on
rainy outdoor shots, hard cuts every 2-4 s — with a headline at the top and one subtitle line at the bottom.
"""

from __future__ import annotations

import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from ..config import FONT_DISPLAY_MEDIUM_PATH, FONT_DISPLAY_PATH, FONT_PATH, FPS, OUTPUT_DIR, VIDEO_H, VIDEO_W
from . import doodle_cast as dc
from .doodle import BG_DIR, FICTION
from .render import _Writer, _mix, _scaled, _subtitle_chunks, _text_block

W, H = VIDEO_W, VIDEO_H
FLOOR = 1560                       # where feet stand in a wide shot
BOIL = 4                           # frames per line-boil variant
OUTDOOR = ("street", "parking_lot", "bus_stop", "rooftop", "market", "entrance", "alley")


# ---------------------------------------------------------------------------
# Backgrounds
# ---------------------------------------------------------------------------
def stylize(img: Image.Image) -> Image.Image:
    """Real photo → flat, cool, cel-like plate: details (plates, faces, signs) melt into flat shapes."""
    im = ImageOps.fit(img.convert("RGB"), (W, H), Image.LANCZOS)
    im = im.filter(ImageFilter.MedianFilter(7)).filter(ImageFilter.GaussianBlur(2))
    im = ImageEnhance.Color(im).enhance(0.35)
    im = ImageOps.posterize(im, 3).filter(ImageFilter.GaussianBlur(1.2))
    im = Image.blend(im, Image.new("RGB", im.size, (150, 170, 200)), 0.30)
    return ImageEnhance.Contrast(im).enhance(0.9)


def _bg_for(place: str, used: dict) -> tuple[str, Image.Image]:
    files = sorted(BG_DIR.glob(f"{place}_*.jpg")) or sorted(BG_DIR.glob("*.jpg"))
    if not files:
        return "", Image.new("RGB", (W, H), (150, 165, 190))
    if place not in used:
        used[place] = random.Random(place).choice(files)
    f = used[place]
    img = Image.open(f).convert("RGB")
    return f.name, img if img.size == (W, H) else stylize(img)


def _rain(seed: int) -> list[Image.Image]:
    rng = random.Random(seed)
    drops = [(rng.uniform(0, W), rng.uniform(0, H), rng.uniform(40, 90)) for _ in range(140)]
    frames = []
    for k in range(10):
        img = Image.new("RGBA", (W, H))
        d = ImageDraw.Draw(img)
        for x, y, ln in drops:
            yy = (y + k * 48) % H
            d.line((x, yy, x - ln * 0.12, yy + ln), fill=(235, 240, 255, 110), width=3)
        frames.append(img)
    return frames


# ---------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------
def _headline(text: str) -> Image.Image | None:
    t = _text_block(text, FONT_DISPLAY_PATH, 62, (20, 20, 24, 255), max_w=940, max_lines=2, align="center", min_size=40)
    if not t:
        return None
    w, h = t.width + 60, t.height + 30
    img = Image.new("RGBA", (w, h))
    ImageDraw.Draw(img).rounded_rectangle((0, 0, w - 1, h - 1), radius=22, fill=(255, 255, 255, 240))
    img.alpha_composite(t, (30, 12))
    return img


def _shade(top: int, alpha: int) -> Image.Image:
    a = np.zeros((H, W, 4), np.uint8)
    ramp = np.clip((np.arange(H) - top) / 160, 0, 1) * alpha
    a[..., 3] = ramp[:, None].astype(np.uint8)
    return Image.fromarray(a, "RGBA")


def _subtitle(text: str) -> Image.Image | None:
    return _text_block(text, FONT_DISPLAY_MEDIUM_PATH, 58, (255, 255, 255, 255), max_w=980, max_lines=2,
                       stroke=7, align="center", min_size=40)


def _tag(text: str) -> Image.Image | None:
    t = _text_block(text, FONT_DISPLAY_PATH, 54, (255, 255, 255, 255), max_w=600, max_lines=1, min_size=32)
    if not t:
        return None
    img = Image.new("RGBA", (t.width + 50, t.height + 26))
    ImageDraw.Draw(img).rectangle((0, 0, img.width - 1, img.height - 1), fill=(214, 58, 52, 255))
    img.alpha_composite(t, (25, 8))
    return img.rotate(-4, resample=Image.BICUBIC, expand=True)


def _guess_card() -> Image.Image:
    t = _text_block("ทายสิ ผมทำยังไง?", FONT_DISPLAY_PATH, 96, (20, 20, 24, 255), max_w=900, max_lines=1)
    img = Image.new("RGBA", (t.width + 90, t.height + 60))
    ImageDraw.Draw(img).rounded_rectangle((0, 0, img.width - 1, img.height - 1), radius=30, fill=(255, 214, 64, 255),
                                          outline=(20, 20, 24, 255), width=6)
    img.alpha_composite(t, (45, 22))
    return img.rotate(3, resample=Image.BICUBIC, expand=True)


# ---------------------------------------------------------------------------
class _Sprites:
    def __init__(self, cast: list[dict]):
        self.looks = [dc.Look(c["hair"], c["glasses"], c["color"], 1.0 if k == 0 else 0.94 + 0.06 * (k % 3))
                      for k, c in enumerate(cast)]
        self.cache: dict = {}

    def get(self, who: int, expr: str, pose: str, facing: int, f: int) -> Image.Image:
        key = (who, expr, pose, facing, (f // BOIL) % 3)
        if key not in self.cache:
            self.cache[key] = dc.draw(self.looks[who], expr, pose, key[-1], facing)
        return self.cache[key]


def _shots(n: int, close_ok: bool) -> list[tuple[int, int, str]]:
    """Split a beat into hard-cut shots of 2-4 s: wide first, then a closer framing."""
    if n < FPS * 3.6 or not close_ok:
        return [(0, n, "wide")]
    cut = n // 2
    return [(0, cut, "wide"), (cut, n, "close")]


def render(plan, beat_durs: list[float], voice: Path, run_dir: Path, out_name: str) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    silent = run_dir / "story_silent.mp4"
    writer = _Writer(silent, sum(beat_durs))
    sprites = _Sprites(plan.cast)
    headline = _headline(plan.title)
    fiction = _text_block("เรื่องสมมติ", FONT_DISPLAY_MEDIUM_PATH, 30, (255, 255, 255, 200), max_w=300, max_lines=1,
                          stroke=3)
    footer = _text_block(FICTION, FONT_PATH, 24, (255, 255, 255, 160), max_w=1000, max_lines=1, min_size=18, stroke=2)
    rain = _rain(5)
    guess = _guess_card()
    marks = {(kind, v): dc.wobble_marks(v, kind) for kind in ("shock", "angry") for v in range(3)}
    shade = _shade(1560, 120)
    used_bg: dict = {}
    bg_cache: dict = {}
    seen: set[int] = set()
    rng = random.Random(len(plan.title))
    pops: list[float] = []
    t0 = 0.0

    for i, (sc, d) in enumerate(zip(plan.scenes, beat_durs)):
        n = max(int(round(d * FPS)), 1)
        if sc.place not in bg_cache:
            bg_cache[sc.place] = _bg_for(sc.place, used_bg)
        sc.bg_file, bg = bg_cache[sc.place]
        chunks = _subtitle_chunks(sc.narration, max_chars=40)
        bounds = np.cumsum([max(len(c), 1) for c in chunks]) / sum(max(len(c), 1) for c in chunks) * n
        subs = [_subtitle(c) for c in chunks]
        tag = _tag(sc.punch) if sc.punch else None
        people = sc.people
        if sc.visual in ("guess", "twist"):
            pops.append(t0 + 0.1)
        print(f"    [render] beat {i + 1}/{len(plan.scenes)} {sc.visual} {sc.place} {d:.1f}s {people}")

        for s0, s1, framing in _shots(n, close_ok=len(people) >= 1):
            pan = (rng.uniform(-60, 60), rng.uniform(-40, 40))
            z0 = rng.uniform(1.04, 1.1) if framing == "wide" else rng.uniform(1.18, 1.26)
            focus = people[-1][0] if framing == "close" and len(people) > 1 else people[0][0]
            for f in range(s0, s1):
                t = (f - s0) / max(s1 - s0 - 1, 1)
                z = z0 + 0.04 * t
                w2, h2 = W / z, H / z
                cx, cy = W / 2 + pan[0] * t, H / 2 + pan[1] * t
                frame = bg.transform((W, H), Image.EXTENT, (cx - w2 / 2, cy - h2 / 2, cx + w2 / 2, cy + h2 / 2),
                                     Image.BILINEAR).convert("RGBA")
                if plan.rain and sc.place in OUTDOOR:
                    frame.alpha_composite(rain[f % len(rain)])

                if framing == "wide":
                    slots = [W / 2] if len(people) == 1 else [W * 0.3, W * 0.7]
                    for (who, expr, pose), x in zip(people, slots):
                        facing = 1 if x < W / 2 or len(people) == 1 else -1
                        spr = _scaled(sprites.get(who, expr, pose, facing, f), 1.15)
                        enter = 0.0
                        if who not in seen:                                # first appearance: slide in
                            enter = 1 - min(f / 10, 1)
                        bob = 4 * math.sin((f + who * 11) / 9)
                        sx = int(x - spr.width / 2 + enter * (-500 if x < W / 2 else 500))
                        sy = int(FLOOR - spr.height + bob)
                        frame.alpha_composite(spr, (sx, sy))
                        if expr in ("shock", "angry"):
                            mk = marks[(expr, (f // BOIL) % 3)]
                            frame.alpha_composite(mk, (sx + spr.width - 70, sy + 10))
                else:
                    who, expr, pose = next(p for p in people if p[0] == focus)
                    spr = _scaled(sprites.get(who, expr, pose, 1, f), 1.75)
                    bob = 5 * math.sin(f / 9)
                    sx, sy = int(W / 2 - spr.width / 2), int(420 + bob)            # head and torso fill the frame
                    frame.alpha_composite(spr, (sx, sy))
                    if expr in ("shock", "angry"):
                        mk = _scaled(marks[(expr, (f // BOIL) % 3)], 1.5)
                        frame.alpha_composite(mk, (sx + spr.width - 120, sy + 20))

                frame.alpha_composite(shade)                                # soft shade behind the subtitle
                if headline is not None:
                    frame.alpha_composite(headline, ((W - headline.width) // 2, 110))
                if tag is not None and f >= 3:
                    frame.alpha_composite(tag, (70, 120 + (headline.height if headline else 0) + 40))
                if sc.visual == "guess":
                    k = min(f / 6, 1)
                    gs = _scaled(guess, 1.3 - 0.3 * k) if k < 1 else guess
                    frame.alpha_composite(gs, ((W - gs.width) // 2, 640))
                if fiction is not None:
                    frame.alpha_composite(fiction, (W - fiction.width - 30, 40))
                sub = subs[min(int(np.searchsorted(bounds, f, side="right")), len(subs) - 1)]
                if sub is not None:
                    frame.alpha_composite(sub, ((W - sub.width) // 2, 1660))
                if footer is not None and i == len(plan.scenes) - 1:
                    frame.alpha_composite(footer, ((W - footer.width) // 2, H - 70))
                writer.write(frame)
        seen.update(p[0] for p in people)
        t0 += d

    writer.close()
    return _mix(silent, voice, beat_durs, OUTPUT_DIR / out_name, run_dir, pops)
