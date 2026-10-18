"""
Still-frame preparation for the local renderer.

prepare_frame()  any source image -> 1080x1920 JPEG. Near-9:16 images are
                 cover-cropped; anything else (square product shots, landscape
                 maps) is fitted over a blurred, darkened copy of itself so
                 nothing important gets cropped away.
globe_card()     designed fallback visual for Flow B (chart-ink + graticule).
product_card()   designed fallback visual for Flow A when a row has no image.
"""

from __future__ import annotations

import math
from pathlib import Path

from .captions import _fit, _font, _hex
from .config import SHOPEE_ORANGE, STORY_ACCENT, STORY_INK, VIDEO_H, VIDEO_W

_TARGET = VIDEO_W / VIDEO_H


def _cover(img, w: int, h: int):
    from PIL import Image
    s = max(w / img.width, h / img.height)
    r = img.resize((max(int(img.width * s), w), max(int(img.height * s), h)), Image.LANCZOS)
    x, y = (r.width - w) // 2, (r.height - h) // 2
    return r.crop((x, y, x + w, y + h))


def prepare_frame(src: Path, out: Path, *, mode: str = "auto", focus_y: float = 0.44,
                  max_h_ratio: float = 0.60) -> Path:
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

    img = Image.open(src).convert("RGB")
    ratio = img.width / img.height
    if mode == "cover" or (mode == "auto" and abs(ratio - _TARGET) < 0.07):
        _cover(img, VIDEO_W, VIDEO_H).save(out, quality=92)
        return out

    bg = _cover(img, VIDEO_W, VIDEO_H).filter(ImageFilter.GaussianBlur(42))
    bg = ImageEnhance.Brightness(bg).enhance(0.5)

    max_w, max_h = int(VIDEO_W * 0.94), int(VIDEO_H * max_h_ratio)
    s = min(max_w / img.width, max_h / img.height)
    fg = img.resize((max(int(img.width * s), 1), max(int(img.height * s), 1)), Image.LANCZOS)

    mask = Image.new("L", fg.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, fg.width, fg.height), radius=30, fill=255)
    x = (VIDEO_W - fg.width) // 2
    y = int(VIDEO_H * focus_y - fg.height / 2)

    shadow = Image.new("RGBA", (VIDEO_W, VIDEO_H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        (x + 6, y + 18, x + fg.width + 6, y + fg.height + 18), radius=34, fill=(0, 0, 0, 150))
    shadow = shadow.filter(ImageFilter.GaussianBlur(24))
    canvas = Image.alpha_composite(bg.convert("RGBA"), shadow)
    canvas.paste(fg, (x, y), mask)
    canvas.convert("RGB").save(out, quality=92)
    return out


def _gradient(top: str, bottom: str):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (VIDEO_W, VIDEO_H))
    d = ImageDraw.Draw(img)
    a, b = _hex(top), _hex(bottom)
    for y in range(VIDEO_H):
        t = y / (VIDEO_H - 1)
        d.line([(0, y), (VIDEO_W, y)], fill=tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)))
    return img


def globe_card(out: Path, *, highlight: str = "", seed: int = 0) -> Path:
    """Chart-ink background with an orthographic globe graticule and an
    optional big highlight (a year, a distance, a keyword) in map-gold."""
    from PIL import Image, ImageDraw

    img = _gradient(STORY_INK, "#06141D").convert("RGBA")
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy, r = VIDEO_W // 2, int(VIDEO_H * 0.46), 600
    gold = _hex(STORY_ACCENT, 70)
    faint = _hex(STORY_ACCENT, 34)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=gold, width=4)
    tilt = (seed % 6) * 7
    for lon in range(-75, 90, 15):
        rx = abs(r * math.sin(math.radians(lon + tilt)))
        if rx > 4:
            d.ellipse((cx - rx, cy - r, cx + rx, cy + r), outline=faint, width=2)
    for lat in range(-60, 75, 15):
        y = cy - r * math.sin(math.radians(lat))
        half = r * math.cos(math.radians(lat))
        d.line([(cx - half, y), (cx + half, y)], fill=faint, width=2)
    img = Image.alpha_composite(img, layer)

    if highlight:
        draw = ImageDraw.Draw(img)
        font, lines, size = _fit(highlight, 150, VIDEO_W - 160, 2, draw)
        y = cy - (int(size * 1.25) * len(lines)) // 2
        for ln in lines:
            w = draw.textlength(ln, font=font)
            draw.text(((VIDEO_W - w) / 2 + 4, y + 5), ln, font=font, fill=(0, 0, 0, 160))
            draw.text(((VIDEO_W - w) / 2, y), ln, font=font, fill=_hex(STORY_ACCENT))
            y += int(size * 1.25)
    img.convert("RGB").save(out, quality=92)
    return out


def product_card(out: Path, *, name: str, price: str) -> Path:
    """Shopee-orange card with the product name and price (no-image fallback)."""
    from PIL import ImageDraw

    img = _gradient(SHOPEE_ORANGE, "#B8321A").convert("RGBA")
    draw = ImageDraw.Draw(img)
    font, lines, size = _fit(name, 78, VIDEO_W - 160, 4, draw)
    y = int(VIDEO_H * 0.30)
    for ln in lines:
        w = draw.textlength(ln, font=font)
        draw.text(((VIDEO_W - w) / 2, y), ln, font=font, fill=(255, 255, 255, 255))
        y += int(size * 1.35)
    if price:
        pfont = _font(132)
        label = f"฿{price}"
        w = draw.textlength(label, font=pfont)
        draw.text(((VIDEO_W - w) / 2, y + 60), label, font=pfont, fill=(255, 241, 214, 255))
    img.convert("RGB").save(out, quality=92)
    return out
