"""
Hand-drawn-looking doodle characters for the "doodle" style: round white face, dot eyes, a tube body,
stick legs, and one identity feature (glasses, hair, cap, bun). Every stroke is jittered, and each
pose is drawn in a few "boil" variants that the renderer cycles, so the lines shimmer like real
hand-drawn animation instead of looking like clean vector clip art.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from PIL import Image, ImageDraw

S = 2                                   # supersampling
W, H = 360, 760                         # sprite size (feet at the bottom edge)
LINE = (28, 28, 32, 255)
WHITE = (250, 250, 248, 255)
SKIN_SHADE = (226, 226, 222, 255)

HAIRS = ("short", "long", "bun", "cap", "bald", "spiky")
COLORS = {"blue": (86, 128, 196), "red": (204, 82, 74), "green": (92, 150, 104), "yellow": (232, 186, 70),
          "grey": (140, 140, 148), "purple": (136, 100, 170), "orange": (226, 132, 62), "black": (60, 60, 66)}
EXPRESSIONS = ("neutral", "angry", "shock", "smug", "sad", "happy")
POSES = ("stand", "point", "arms_up", "walk", "phone")


@dataclass(frozen=True)
class Look:
    hair: str = "short"
    glasses: bool = False
    color: str = "blue"
    height: float = 1.0


def _jit(rng, pts, amt=2.2):
    return [(x + rng.uniform(-amt, amt), y + rng.uniform(-amt, amt)) for x, y in pts]


def _line(d, rng, pts, width=6, fill=LINE, amt=2.0):
    """A wobbly stroke through pts, subdivided so the wobble reads as hand drawn."""
    out = []
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        n = max(int(math.hypot(x1 - x0, y1 - y0) / 18), 1)
        out += [(x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n) for k in range(n)]
    out.append(pts[-1])
    out = _jit(rng, out, amt)
    d.line([(x * S, y * S) for x, y in out], fill=fill, width=width * S, joint="curve")
    r = width * S / 2
    for x, y in (out[0], out[-1]):
        d.ellipse((x * S - r, y * S - r, x * S + r, y * S + r), fill=fill)


def _blob(d, rng, cx, cy, rx, ry, fill, width=6, amt=2.2, n=48):
    pts = [(cx + rx * math.cos(2 * math.pi * k / n), cy + ry * math.sin(2 * math.pi * k / n)) for k in range(n)]
    pts = _jit(rng, pts, amt)
    sp = [(x * S, y * S) for x, y in pts]
    d.polygon(sp, fill=fill)
    d.line(sp + [sp[0]], fill=LINE, width=width * S, joint="curve")


def draw(look: Look, expression: str = "neutral", pose: str = "stand", variant: int = 0,
         facing: int = 1) -> Image.Image:
    rng = random.Random(hash((look, expression, pose, variant)) & 0xFFFFFFFF)
    img = Image.new("RGBA", (W * S, H * S))
    d = ImageDraw.Draw(img)
    k = look.height
    cx = W / 2
    foot = H - 14
    hip = foot - 230 * k
    neck = hip - 230 * k
    head_r = 92
    hy = neck - head_r + 14
    body = COLORS.get(look.color, COLORS["blue"]) + (255,)

    # legs
    stride = 34 if pose == "walk" else 0
    for side, s2 in ((-1, -stride), (1, stride)):
        x = cx + side * 30
        _line(d, rng, [(x, hip - 10), (x + s2 * 0.5, hip + 110 * k), (x + s2, foot)], width=7)
        _line(d, rng, [(x + s2, foot), (x + s2 + 26 * facing, foot)], width=7)
    # tube body
    tw = 74
    pts = [(cx - tw, neck + 30), (cx - tw - 6, hip), (cx + tw + 6, hip), (cx + tw, neck + 30)]
    top = [(cx + tw * math.cos(math.pi * t / 12), neck + 30 - 34 * math.sin(math.pi * t / 12)) for t in range(13)]
    shape = _jit(rng, [pts[0], pts[1], pts[2], pts[3]] + top, 2.0)
    d.polygon([(x * S, y * S) for x, y in shape], fill=body)
    d.line([(x * S, y * S) for x, y in shape + [shape[0]]], fill=LINE, width=6 * S, joint="curve")
    # arms
    sh_y = neck + 50
    for side in (-1, 1):
        sx = cx + side * (tw - 6)
        front = side == facing
        if pose == "arms_up":
            arm = [(sx, sh_y), (sx + side * 60, sh_y - 70), (sx + side * 70, sh_y - 150)]
        elif pose == "point" and front:
            arm = [(sx, sh_y), (sx + side * 90, sh_y + 10), (sx + side * 170, sh_y - 10)]
        elif pose == "phone" and front:
            arm = [(sx, sh_y), (sx + side * 40, sh_y + 70), (sx + side * 10 - side * 30, sh_y - 30)]
        else:
            swing = (18 if pose == "walk" else 6) * (1 if side > 0 else -1)
            arm = [(sx, sh_y), (sx + side * 26 + swing, sh_y + 90), (sx + side * 20 + swing, sh_y + 170)]
        _line(d, rng, arm, width=7)
        if pose == "phone" and front:
            px, py = arm[-1]
            d.rounded_rectangle(((px - 14) * S, (py - 26) * S, (px + 14) * S, (py + 26) * S), radius=5 * S,
                                fill=(40, 40, 46, 255))

    # head
    _blob(d, rng, cx, hy, head_r, head_r * 0.96, WHITE)
    # hair / identity
    if look.hair == "short":
        _blob(d, rng, cx, hy - 58, 82, 40, LINE, width=2)
    elif look.hair == "spiky":
        spikes = [(cx - 80 + 20 * i, hy - 60 - (30 if i % 2 else 0)) for i in range(9)]
        d.polygon([((cx - 86) * S, (hy - 40) * S)] + [(x * S, y * S) for x, y in _jit(rng, spikes)]
                  + [((cx + 86) * S, (hy - 40) * S)], fill=LINE)
    elif look.hair == "long":
        _blob(d, rng, cx, hy - 50, 92, 50, LINE, width=2)
        for side in (-1, 1):
            _line(d, rng, [(cx + side * 86, hy - 40), (cx + side * 100, hy + 40), (cx + side * 92, hy + 110)],
                  width=26)
    elif look.hair == "bun":
        _blob(d, rng, cx, hy - 56, 84, 38, LINE, width=2)
        _blob(d, rng, cx + 10, hy - 116, 34, 30, LINE, width=2)
    elif look.hair == "cap":
        _blob(d, rng, cx, hy - 54, 90, 44, body, width=6)
        _line(d, rng, [(cx + facing * 40, hy - 40), (cx + facing * 140, hy - 36)], width=12, fill=body)
        _line(d, rng, [(cx + facing * 40, hy - 32), (cx + facing * 140, hy - 30)], width=4)

    # face (shifted toward facing)
    fx = cx + facing * 14
    ey = hy + 4
    if expression == "shock":
        for ex in (fx - 30, fx + 30):
            _blob(d, rng, ex, ey, 13, 15, WHITE, width=4, amt=1)
            d.ellipse(((ex - 4) * S, (ey - 4) * S, (ex + 4) * S, (ey + 4) * S), fill=LINE)
        _blob(d, rng, fx, ey + 44, 12, 15, LINE, width=2, amt=1)
    elif expression == "happy":
        for ex in (fx - 30, fx + 30):
            d.arc(((ex - 12) * S, (ey - 8) * S, (ex + 12) * S, (ey + 10) * S), 200, 340, fill=LINE, width=5 * S)
        d.arc(((fx - 24) * S, (ey + 18) * S, (fx + 24) * S, (ey + 50) * S), 20, 160, fill=LINE, width=5 * S)
    else:
        for ex in (fx - 30, fx + 30):
            r = 7 if expression != "smug" else 6
            d.ellipse(((ex - r) * S, (ey - r) * S, (ex + r) * S, (ey + r) * S), fill=LINE)
        if expression == "angry":
            _line(d, rng, [(fx - 46, ey - 26), (fx - 14, ey - 14)], width=5, amt=1)
            _line(d, rng, [(fx + 46, ey - 26), (fx + 14, ey - 14)], width=5, amt=1)
            _line(d, rng, [(fx - 18, ey + 46), (fx + 18, ey + 40)], width=5, amt=1)
        elif expression == "sad":
            _line(d, rng, [(fx - 44, ey - 16), (fx - 16, ey - 26)], width=4, amt=1)
            _line(d, rng, [(fx + 44, ey - 16), (fx + 16, ey - 26)], width=4, amt=1)
            d.arc(((fx - 18) * S, (ey + 38) * S, (fx + 18) * S, (ey + 60) * S), 200, 340, fill=LINE, width=4 * S)
        elif expression == "smug":
            _line(d, rng, [(fx - 46, ey - 20), (fx - 14, ey - 20)], width=4, amt=1)
            _line(d, rng, [(fx + 14, ey - 22), (fx + 46, ey - 28)], width=4, amt=1)
            d.arc(((fx - 10) * S, (ey + 26) * S, (fx + 34) * S, (ey + 50) * S), 10, 150, fill=LINE, width=5 * S)
        else:
            _line(d, rng, [(fx - 14, ey + 44), (fx + 14, ey + 44)], width=5, amt=1)
    if look.glasses:
        for ex in (fx - 30, fx + 30):
            _blob(d, rng, ex, ey, 22, 19, (0, 0, 0, 0), width=4, amt=1)
        _line(d, rng, [(fx - 8, ey - 2), (fx + 8, ey - 2)], width=4, amt=0.5)
    return img.resize((W, H), Image.LANCZOS)


def wobble_marks(variant: int, kind: str = "shock") -> Image.Image:
    """Little stress/shock strokes drawn beside a head."""
    rng = random.Random(variant * 7 + (1 if kind == "angry" else 0))
    img = Image.new("RGBA", (160 * S, 160 * S))
    d = ImageDraw.Draw(img)
    if kind == "angry":                                         # a scribbled anger vein
        for a in (0, 90, 180, 270):
            r = math.radians(a + 45)
            x, y = 80 + 34 * math.cos(r), 80 + 34 * math.sin(r)
            _line(d, rng, [(x, y), (x + 22 * math.cos(r + 1.2), y + 22 * math.sin(r + 1.2))], width=7,
                  fill=(210, 50, 50, 255), amt=1.5)
    else:
        for k in range(3):
            a = math.radians(-60 + k * 30)
            _line(d, rng, [(40 + 40 * math.cos(a), 90 + 40 * math.sin(a)), (40 + 90 * math.cos(a), 90 + 90 * math.sin(a))],
                  width=6, amt=1.5)
    return img.resize((160, 160), Image.LANCZOS)


if __name__ == "__main__":
    import sys
    looks = [Look("short", True, "blue"), Look("long", False, "red"), Look("cap", False, "green", 1.05),
             Look("bun", True, "yellow", 0.92), Look("spiky", False, "purple"), Look("bald", False, "grey", 1.08)]
    sheet = Image.new("RGBA", (W * 6, H * 2), (200, 212, 226, 255))
    for i, lk in enumerate(looks):
        sheet.alpha_composite(draw(lk, EXPRESSIONS[i], POSES[i % len(POSES)]), (i * W, 0))
        sheet.alpha_composite(draw(lk, "neutral", "stand", facing=-1), (i * W, H))
    sheet.save(sys.argv[1] if len(sys.argv) > 1 else "doodle_sheet.png")
