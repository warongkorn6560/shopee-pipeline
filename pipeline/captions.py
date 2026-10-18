"""
Render on-screen text to transparent 1080x1920 PNGs with Pillow; FFmpeg then
overlays each PNG at 0,0.

Why PNG overlays instead of ffmpeg drawtext:
  - Portable ffmpeg builds often lack libfreetype (no drawtext filter).
  - Pillow gives nicer typography: rounded translucent boxes, drop shadows.
  - With libraqm present, Pillow shapes Thai correctly (stacked vowel/tone marks).
"""

from __future__ import annotations

from pathlib import Path

from .config import FONT_PATH, FONT_REGULAR_PATH, VIDEO_H, VIDEO_W, WORK_DIR

# Thai marks that must stay attached to the preceding character, and leading
# vowels that must stay attached to the following one. Breaking a line between
# them renders orphaned marks.
_NO_BREAK_BEFORE = set(
    "ะัาำิีึืฺุู"
    "ๅๆ็่้๊๋์ํ๎"
)
_NO_BREAK_AFTER = set("เแโใไ")


def _font(size: int, *, regular: bool = False):
    from PIL import ImageFont
    path = FONT_REGULAR_PATH if regular else FONT_PATH
    try:
        return ImageFont.truetype(str(path), size, layout_engine=ImageFont.Layout.RAQM)
    except Exception:
        return ImageFont.truetype(str(path), size)


def _clusters(text: str) -> list[str]:
    out: list[str] = []
    for ch in text:
        if out and (ch in _NO_BREAK_BEFORE or out[-1][-1] in _NO_BREAK_AFTER):
            out[-1] += ch
        else:
            out.append(ch)
    return out


def _clean(text: str) -> str:
    """Keep only what Sarabun can draw (Thai, Latin, common punctuation);
    emoji and pictographs would render as empty boxes."""
    keep = []
    for ch in text.replace("\\n", "\n"):
        o = ord(ch)
        if ch == "\n" or 0x20 <= o < 0x250 or 0x0E00 <= o <= 0x0E7F or 0x2010 <= o <= 0x2027:
            keep.append(ch)
    lines = [" ".join(ln.split()) for ln in "".join(keep).split("\n")]
    return "\n".join(ln for ln in lines if ln)


def _wrap(text: str, font, max_width: int, draw) -> list[str]:
    """Greedy wrap on spaces; break long unspaced Thai runs between clusters."""
    return _wrap_ex(text, font, max_width, draw)[0]


def _wrap_ex(text: str, font, max_width: int, draw) -> tuple[list[str], bool]:
    lines, cur = [], ""
    for w in text.split(" "):
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=font) <= max_width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    out, hard = [], False
    for ln in lines:
        if draw.textlength(ln, font=font) <= max_width:
            out.append(ln)
            continue
        hard = True
        buf = ""
        for cl in _clusters(ln):
            if draw.textlength(buf + cl, font=font) <= max_width or not buf:
                buf += cl
            else:
                out.append(buf)
                buf = cl
        if buf:
            out.append(buf)
    return out, hard


def _fit(text: str, size: int, max_width: int, max_lines: int, draw, *, regular=False):
    """Shrink the font until the text fits in max_lines without splitting a
    word (Thai has no hyphenation, so a mid-word break reads as a typo)."""
    text = _clean(text)
    min_size = max(30, int(size * 0.5))
    while True:
        font = _font(size, regular=regular)
        lines: list[str] = []
        hard = False
        for raw in text.split("\n"):
            wrapped, broke = _wrap_ex(raw, font, max_width, draw)
            lines.extend(wrapped)
            hard = hard or broke
        if (len(lines) <= max_lines and not hard) or size <= min_size:
            return font, lines, size
        size -= 4


def _hex(color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    c = color.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), alpha


def _vertical_fade(img, top: int, bottom: int, max_alpha: int, *, downward: bool):
    from PIL import Image, ImageDraw
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    span = max(bottom - top, 1)
    for y in range(top, bottom):
        t = (y - top) / span
        a = int(max_alpha * ((1 - t) if downward else t))
        d.line([(0, y), (VIDEO_W, y)], fill=(0, 0, 0, a))
    return Image.alpha_composite(img, layer)


def render_overlay(caption: str, out: Path, *, big: bool = False, position: str = "lower",
                   header: str = "", badge: str = "", credit: str = "",
                   accent: str = "#F2B544", caption_y: float = 0.78) -> Path:
    """
    Full-frame transparent PNG: optional series badge + header at the top, the
    caption on a translucent rounded box, and a small credit line at the bottom.
    """
    from PIL import Image, ImageDraw

    WORK_DIR.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGBA", (VIDEO_W, VIDEO_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if header or badge:
        img = _vertical_fade(img, 0, 560, 175, downward=True)
        draw = ImageDraw.Draw(img)
        y = 150
        if badge:
            bfont = _font(34)
            tw = draw.textlength(badge, font=bfont)
            px, ph = 26, 58
            draw.rounded_rectangle((70, y, 70 + tw + px * 2, y + ph), radius=ph // 2,
                                   fill=_hex(accent))
            draw.text((70 + px, y + 7), badge, font=bfont, fill=(20, 20, 20, 255))
            y += ph + 22
        if header:
            hfont, hlines, hsize = _fit(header, 60, VIDEO_W - 140, 2, draw)
            for ln in hlines:
                draw.text((72, y + 3), ln, font=hfont, fill=(0, 0, 0, 170))
                draw.text((70, y), ln, font=hfont, fill=(255, 255, 255, 255))
                y += int(hsize * 1.32)

    if credit:
        img = _vertical_fade(img, VIDEO_H - 170, VIDEO_H, 150, downward=False)
        draw = ImageDraw.Draw(img)
        cfont, clines, csize = _fit(credit, 26, VIDEO_W - 120, 2, draw, regular=True)
        y = VIDEO_H - 60 - int(csize * 1.3) * len(clines)
        for ln in clines:
            w = draw.textlength(ln, font=cfont)
            draw.text(((VIDEO_W - w) / 2, y), ln, font=cfont, fill=(255, 255, 255, 190))
            y += int(csize * 1.3)

    max_w = int(VIDEO_W * 0.84)
    font, lines, size = _fit(caption or "", 104 if big else 66, max_w, 4 if big else 3, draw)
    if lines:
        line_h = int(size * 1.38)
        block_h = line_h * len(lines)
        cy = int(VIDEO_H * (0.5 if position == "center" else caption_y))
        top = cy - block_h // 2
        pad = 34
        widths = [draw.textlength(ln, font=font) for ln in lines]
        box_w = int(max(widths) + pad * 2)
        box_x0 = (VIDEO_W - box_w) // 2
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(layer).rounded_rectangle(
            (box_x0, top - pad, box_x0 + box_w, top + block_h + pad),
            radius=36, fill=(0, 0, 0, 150))
        img = Image.alpha_composite(img, layer)
        draw = ImageDraw.Draw(img)
        y = top
        for ln, w in zip(lines, widths):
            x = (VIDEO_W - w) / 2
            draw.text((x + 3, y + 3), ln, font=font, fill=(0, 0, 0, 180))
            draw.text((x, y), ln, font=font, fill=(255, 255, 255, 255))
            y += line_h

    img.save(out)
    return out


def render_caption(text: str, out: Path, *, big: bool = False,
                   position: str = "lower") -> Path:
    """Caption-only overlay (Flow A)."""
    return render_overlay(text, out, big=big, position=position, caption_y=0.80)
