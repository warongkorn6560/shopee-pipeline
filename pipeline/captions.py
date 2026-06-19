"""
Render caption text to transparent PNGs with Pillow, then ffmpeg overlays them.

Why PNG overlays instead of ffmpeg drawtext:
  - Homebrew/portable ffmpeg builds often lack libfreetype (no drawtext filter).
  - Pillow gives nicer typography: rounded translucent boxes, drop shadows.
  - With libraqm present, Pillow shapes Thai correctly (stacked vowel/tone marks).

render_caption() produces a full 1080x1920 transparent PNG with the text placed
where it should appear, so the ffmpeg overlay is a trivial 0,0 composite.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from .config import FONT_PATH, VIDEO_H, VIDEO_W, WORK_DIR


def _font(size: int):
    from PIL import ImageFont
    # layout_engine raqm if available -> correct Thai shaping; else default.
    try:
        from PIL import ImageFont as _IF
        return ImageFont.truetype(str(FONT_PATH), size, layout_engine=_IF.Layout.RAQM)
    except Exception:
        return ImageFont.truetype(str(FONT_PATH), size)


def _wrap(text: str, font, max_width: int, draw) -> list[str]:
    """Greedy word-wrap that also breaks very long unbroken Thai runs."""
    words = text.split(" ")
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=font) <= max_width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    # hard-break any line still too wide (Thai has few spaces)
    out = []
    for ln in lines:
        if draw.textlength(ln, font=font) <= max_width:
            out.append(ln)
            continue
        buf = ""
        for ch in ln:
            if draw.textlength(buf + ch, font=font) <= max_width or not buf:
                buf += ch
            else:
                out.append(buf)
                buf = ch
        if buf:
            out.append(buf)
    return out


def render_caption(text: str, out: Path, *, big: bool = False,
                   position: str = "lower") -> Path:
    """
    Create a 1080x1920 transparent PNG with `text` drawn on a translucent
    rounded box. position: 'lower' (~78% height) or 'center'.
    """
    from PIL import Image, ImageDraw

    WORK_DIR.mkdir(parents=True, exist_ok=True)
    text = text.replace("\\n", "\n")
    fontsize = 104 if big else 66
    font = _font(fontsize)

    img = Image.new("RGBA", (VIDEO_W, VIDEO_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # wrap each explicit line
    max_w = int(VIDEO_W * 0.86)
    lines: list[str] = []
    for raw in text.split("\n"):
        raw = raw.strip()
        if raw:
            lines.extend(_wrap(raw, font, max_w, draw))

    if not lines:
        img.save(out)
        return out

    line_h = int(fontsize * 1.38)
    block_h = line_h * len(lines)
    cy = int(VIDEO_H * (0.5 if position == "center" else 0.80))
    top = cy - block_h // 2

    # translucent rounded box behind the whole block
    pad = 34
    widths = [draw.textlength(ln, font=font) for ln in lines]
    box_w = int(max(widths) + pad * 2)
    box_x0 = (VIDEO_W - box_w) // 2
    box = (box_x0, top - pad, box_x0 + box_w, top + block_h + pad)
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle(box, radius=36, fill=(0, 0, 0, 150))
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    # draw each line centered, with a soft shadow
    y = top
    for ln, w in zip(lines, widths):
        x = (VIDEO_W - w) / 2
        draw.text((x + 3, y + 3), ln, font=font, fill=(0, 0, 0, 180))  # shadow
        draw.text((x, y), ln, font=font, fill=(255, 255, 255, 255))
        y += line_h

    img.save(out)
    return out
