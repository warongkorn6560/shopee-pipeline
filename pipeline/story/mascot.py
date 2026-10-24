"""
"Ranger Lin" — the reaction-style mascot: a pangolin park ranger, drawn in code so it
is identical in every video and needs no image model. Six expressions:
neutral, shock, think, worry, happy, mindblown.

  python -m pipeline.story.mascot     # regenerate assets/mascot/*.png
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

from ..config import ASSETS

EMOTIONS = ("neutral", "shock", "think", "worry", "happy", "mindblown")
OUT = ASSETS / "mascot"

S = 4                    # supersampling factor
SIZE = 512
INK = (34, 24, 20, 255)
MINT = (205, 239, 224, 255)
BROWN = (168, 101, 58, 255)
BROWN_D = (122, 70, 38, 255)
SKIN = (238, 200, 160, 255)
OLIVE = (98, 112, 52, 255)
OLIVE_D = (70, 82, 36, 255)
GOLD = (245, 181, 52, 255)
WHITE = (255, 255, 255, 255)
BLUE = (110, 190, 255, 255)
PINK = (255, 150, 150, 160)


def _p(*xy):
    return [v * S for v in xy]


def _ellipse(d, box, fill, outline=INK, width=7):
    d.ellipse(_p(*box), fill=fill, outline=outline, width=width * S if outline else 0)


def _arc(d, box, start, end, width=8, fill=INK):
    d.arc(_p(*box), start, end, fill=fill, width=width * S)


def _star(d, cx, cy, r, fill):
    pts = []
    for k in range(10):
        a = math.pi / 2 + k * math.pi / 5
        rr = r if k % 2 == 0 else r * 0.45
        pts += [(cx + rr * math.cos(a)) * S, (cy - rr * math.sin(a)) * S]
    d.polygon(pts, fill=fill, outline=INK, width=3 * S)


def draw(emotion: str = "neutral") -> Image.Image:
    img = Image.new("RGBA", (SIZE * S, SIZE * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    _ellipse(d, (6, 6, 506, 506), MINT, outline=None)

    # body + head with scale rows
    _ellipse(d, (96, 380, 416, 600), BROWN)
    _ellipse(d, (106, 150, 406, 430), BROWN)
    for row, y in enumerate((170, 205, 240)):
        for k in range(5 - row % 2):
            x = 150 + k * 52 + (26 if row % 2 else 0)
            _arc(d, (x - 30, y - 18, x + 30, y + 30), 200, 340, width=7, fill=BROWN_D)
    # overlapping scale plates — what makes it read as a pangolin
    for row, y in enumerate((420, 452, 484)):
        for k in range(7):
            x = 118 + k * 46 + (23 if row % 2 else 0)
            d.chord(_p(x - 30, y - 26, x + 30, y + 30), 0, 180, fill=BROWN_D if (k + row) % 2 else BROWN,
                    outline=INK, width=4 * S)
    for side in (-1, 1):
        for k, y in enumerate((250, 292, 334, 376)):
            x = 256 + side * (124 - k * 4)
            d.chord(_p(x - 26, y - 22, x + 26, y + 26), 0, 180, fill=BROWN_D, outline=INK, width=4 * S)
    # face + snout
    _ellipse(d, (150, 260, 362, 452), SKIN)
    _ellipse(d, (222, 380, 290, 440), SKIN, width=6)
    _ellipse(d, (240, 392, 272, 414), INK, outline=None)          # nose

    # ranger hat
    _ellipse(d, (88, 138, 424, 206), OLIVE)
    d.rounded_rectangle(_p(166, 64, 346, 176), radius=40 * S, fill=OLIVE, outline=INK, width=7 * S)
    d.line(_p(170, 150, 342, 150), fill=OLIVE_D, width=10 * S)
    pin = [(256 * S, 136 * S), (238 * S, 104 * S), (274 * S, 104 * S)]
    _ellipse(d, (236, 82, 276, 120), GOLD, width=4)
    d.polygon(pin, fill=GOLD, outline=INK, width=3 * S)
    _ellipse(d, (250, 94, 262, 106), INK, outline=None)

    lx, rx, ey = 210, 302, 318                                    # eye centres
    if emotion in ("neutral", "think", "worry"):
        look = (8, -8) if emotion == "think" else (0, 0)
        for cx in (lx, rx):
            _ellipse(d, (cx - 22, ey - 28, cx + 22, ey + 28), INK, outline=None)
            hx, hy = cx - 6 + look[0], ey - 12 + look[1]
            _ellipse(d, (hx - 8, hy - 8, hx + 8, hy + 8), WHITE, outline=None)
    elif emotion == "shock":
        for cx in (lx, rx):
            _ellipse(d, (cx - 36, ey - 38, cx + 36, ey + 38), WHITE, width=6)
            _ellipse(d, (cx - 10, ey - 10, cx + 10, ey + 10), INK, outline=None)
    elif emotion == "happy":
        for cx in (lx, rx):
            _arc(d, (cx - 28, ey - 18, cx + 28, ey + 30), 200, 340, width=9)
    elif emotion == "mindblown":
        for cx in (lx, rx):
            _ellipse(d, (cx - 38, ey - 40, cx + 38, ey + 40), WHITE, width=6)
            _star(d, cx, ey, 26, GOLD)

    # brows
    if emotion == "worry":
        d.line(_p(182, 268, 232, 254), fill=INK, width=8 * S)
        d.line(_p(330, 268, 280, 254), fill=INK, width=8 * S)
    elif emotion in ("shock", "mindblown"):
        _arc(d, (178, 240, 242, 270), 200, 340, width=7)
        _arc(d, (270, 240, 334, 270), 200, 340, width=7)
    elif emotion == "think":
        d.line(_p(186, 262, 232, 268), fill=INK, width=7 * S)
        _arc(d, (276, 244, 332, 274), 200, 340, width=7)

    # cheeks
    if emotion in ("happy", "neutral", "mindblown"):
        _ellipse(d, (164, 352, 204, 378), PINK, outline=None)
        _ellipse(d, (308, 352, 348, 378), PINK, outline=None)

    # mouth
    if emotion == "neutral":
        _arc(d, (232, 420, 280, 452), 20, 160, width=7)
    elif emotion == "happy":
        d.chord(_p(220, 410, 292, 470), 0, 180, fill=(140, 40, 50, 255), outline=INK, width=6 * S)
    elif emotion in ("shock", "mindblown"):
        _ellipse(d, (238, 424, 274, 468), (140, 40, 50, 255), width=6)
    elif emotion == "worry":
        d.line(_p(232, 444, 244, 436, 256, 444, 268, 436, 280, 444), fill=INK, width=6 * S)
    elif emotion == "think":
        d.line(_p(240, 440, 274, 436), fill=INK, width=7 * S)

    # props
    if emotion == "think":                                        # paw on chin
        _ellipse(d, (300, 418, 372, 478), SKIN)
    if emotion == "worry":                                        # sweat drop
        d.polygon(_p(366, 228, 352, 262, 380, 262), fill=BLUE, outline=INK, width=3 * S)
        _ellipse(d, (350, 248, 382, 280), BLUE, width=3)
    if emotion == "mindblown":                                    # paws on cheeks + sparkles
        _ellipse(d, (120, 360, 188, 424), SKIN)
        _ellipse(d, (324, 360, 392, 424), SKIN)
        for cx, cy, r in ((80, 120, 20), (440, 110, 16), (452, 300, 12)):
            _star(d, cx, cy, r, GOLD)

    img = img.resize((SIZE, SIZE), Image.LANCZOS)
    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).ellipse((6, 6, SIZE - 6, SIZE - 6), fill=255)
    out = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    ImageDraw.Draw(out).ellipse((6, 6, SIZE - 6, SIZE - 6), outline=WHITE, width=14)
    return out


def load(emotion: str) -> Image.Image:
    emotion = emotion if emotion in EMOTIONS else "neutral"
    path = OUT / f"{emotion}.png"
    return Image.open(path).convert("RGBA") if path.exists() else draw(emotion)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for e in EMOTIONS:
        draw(e).save(OUT / f"{e}.png")
        print("saved", OUT / f"{e}.png")
