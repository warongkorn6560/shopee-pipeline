"""
"น้องออม" — the money-theme mascot: a pink piggy bank with a coin slot, drawn in code (like Ranger Lin)
so it is identical in every video. Full body, transparent background, same six expressions:
neutral, shock, think, worry, happy, mindblown.

  python -m pipeline.story.piggy     # regenerate assets/mascot_money/*.png
"""

from __future__ import annotations

import math

from PIL import Image, ImageDraw

from ..config import ASSETS

EMOTIONS = ("neutral", "shock", "think", "worry", "happy", "mindblown")
OUT = ASSETS / "mascot_money"

S = 4
SIZE = 640
INK = (40, 22, 30, 255)
PINK = (255, 168, 190, 255)
PINK_D = (232, 120, 152, 255)
PINK_L = (255, 206, 218, 255)
GOLD = (250, 192, 50, 255)
GOLD_D = (205, 140, 20, 255)
WHITE = (255, 255, 255, 255)
BLUE = (110, 190, 255, 255)
BLUSH = (255, 110, 140, 150)
MOUTH = (150, 40, 60, 255)


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


def coin(r: int = 46) -> Image.Image:
    img = Image.new("RGBA", (r * 2 * S + 8 * S, r * 2 * S + 8 * S))
    d = ImageDraw.Draw(img)
    d.ellipse((4 * S, 4 * S, (r * 2 + 4) * S, (r * 2 + 4) * S), fill=GOLD, outline=INK, width=5 * S)
    d.ellipse((16 * S, 16 * S, (r * 2 - 8) * S, (r * 2 - 8) * S), outline=GOLD_D, width=4 * S)
    d.line(((r + 4) * S, (r - 22) * S, (r + 4) * S, (r + 30) * S), fill=GOLD_D, width=7 * S)
    d.arc(((r - 16) * S, (r - 18) * S, (r + 22) * S, (r + 6) * S), 90, 270, fill=GOLD_D, width=7 * S)
    d.arc(((r - 14) * S, (r + 2) * S, (r + 24) * S, (r + 26) * S), 270, 90, fill=GOLD_D, width=7 * S)
    return img.resize((img.width // S, img.height // S), Image.LANCZOS)


def draw(emotion: str = "neutral") -> Image.Image:
    img = Image.new("RGBA", (SIZE * S, SIZE * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # legs + tail behind the body
    for x in (190, 260, 380, 450):
        d.rounded_rectangle(_p(x - 30, 470, x + 30, 600), radius=24 * S, fill=PINK_D, outline=INK, width=7 * S)
    _arc(d, (530, 300, 600, 370), 120, 420, width=9, fill=PINK_D)
    # body (the piggy bank) + belly shine
    _ellipse(d, (90, 170, 560, 540), PINK)
    _ellipse(d, (150, 210, 300, 300), PINK_L, outline=None)
    # coin slot on the back
    d.rounded_rectangle(_p(270, 178, 380, 198), radius=8 * S, fill=INK)
    # ears
    for side in (-1, 1):
        cx = 320 + side * 120
        d.polygon(_p(cx - 50, 230, cx + side * 40, 120, cx + 50, 230), fill=PINK_D, outline=INK, width=7 * S)
    # snout
    _ellipse(d, (250, 360, 390, 450), PINK_L, width=6)
    _ellipse(d, (282, 390, 302, 420), INK, outline=None)
    _ellipse(d, (338, 390, 358, 420), INK, outline=None)

    lx, rx, ey = 245, 395, 320
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

    if emotion == "worry":
        d.line(_p(215, 270, 265, 256), fill=INK, width=8 * S)
        d.line(_p(425, 270, 375, 256), fill=INK, width=8 * S)
    elif emotion in ("shock", "mindblown"):
        _arc(d, (210, 240, 280, 272), 200, 340, width=7)
        _arc(d, (360, 240, 430, 272), 200, 340, width=7)
    elif emotion == "think":
        d.line(_p(220, 266, 266, 272), fill=INK, width=7 * S)
        _arc(d, (366, 246, 424, 276), 200, 340, width=7)

    if emotion in ("happy", "neutral", "mindblown"):
        _ellipse(d, (170, 370, 220, 400), BLUSH, outline=None)
        _ellipse(d, (420, 370, 470, 400), BLUSH, outline=None)

    if emotion == "neutral":
        _arc(d, (296, 452, 344, 482), 20, 160, width=7)
    elif emotion == "happy":
        d.chord(_p(284, 446, 356, 506), 0, 180, fill=MOUTH, outline=INK, width=6 * S)
    elif emotion in ("shock", "mindblown"):
        _ellipse(d, (302, 456, 338, 500), MOUTH, width=6)
    elif emotion == "worry":
        d.line(_p(296, 476, 308, 468, 320, 476, 332, 468, 344, 476), fill=INK, width=6 * S)
    elif emotion == "think":
        d.line(_p(302, 474, 338, 470), fill=INK, width=7 * S)

    if emotion == "think":                                       # trotter on chin
        _ellipse(d, (360, 440, 430, 500), PINK_D)
    if emotion == "worry":                                       # sweat drop
        d.polygon(_p(486, 220, 472, 256, 500, 256), fill=BLUE, outline=INK, width=3 * S)
        _ellipse(d, (470, 242, 502, 274), BLUE, width=3)
    if emotion == "happy":                                       # coin popping out of the slot
        _ellipse(d, (300, 110, 350, 160), GOLD, width=5)
    if emotion == "mindblown":
        for cx, cy, r in ((90, 120, 22), (560, 110, 18), (590, 280, 14)):
            _star(d, cx, cy, r, GOLD)
    return img.resize((SIZE, SIZE), Image.LANCZOS)


def load(emotion: str) -> Image.Image:
    emotion = emotion if emotion in EMOTIONS else "neutral"
    path = OUT / f"{emotion}.png"
    return Image.open(path).convert("RGBA") if path.exists() else draw(emotion)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for e in EMOTIONS:
        draw(e).save(OUT / f"{e}.png")
        print("saved", OUT / f"{e}.png")
    coin().save(OUT / "coin.png")
