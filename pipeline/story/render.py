"""
Flow B renderer: an animated satellite-map story video.

Every beat is a shot the writer specified: the camera eases over tilted
satellite imagery toward the beat's subject while real OpenStreetMap geometry
is drawn on top (glowing lines that draw themselves, highlighted areas,
numbered pins, geo-anchored Thai labels), with a bold title card and synced
subtitles. Photo beats show a real Commons image with a slow push-in.
Frames are generated in Python and piped to FFmpeg; the soundtrack is the
narration over a ducked music bed with a soft whoosh on each beat change.
"""

from __future__ import annotations

import math
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from ..captions import _clean, _clusters, _wrap_ex
from ..config import (
    ASSETS, FONT_DISPLAY_MEDIUM_PATH, FONT_DISPLAY_PATH, FONT_PATH, FPS, MUSIC_DIR, OUTPUT_DIR,
    STORY_MUSIC, VIDEO_H, VIDEO_W,
)
from . import maps

W, H = VIDEO_W, VIDEO_H
FW, FH = 1600, 2400                      # flat (top-down) frame before the tilt
MID_FLAT_W = 1340                        # flat width visible at the screen's middle row
QUAD = [(0, 0), (FW, 0), (1340, FH), (260, FH)]  # flat points shown at screen TL, TR, BR, BL
CROSSFADE = 8                            # frames blended when the shot type changes
CARD_IN = 9                              # frames for the title card to slide in

CRIMSON = (215, 38, 61)
GOLD = (242, 181, 68)
CYAN = (96, 214, 255)
RED_LINE = (255, 77, 77)
AREA = (242, 194, 48)
THAILAND = (97.3, 5.6, 105.7, 20.5)


# ---------------------------------------------------------------------------
# Perspective (tilted-camera look)
# ---------------------------------------------------------------------------
def _homography(src, dst) -> np.ndarray:
    a = []
    for (x, y), (u, v) in zip(src, dst):
        a.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        a.append([0, 0, 0, x, y, 1, -v * x, -v * y])
    h = np.linalg.solve(np.array(a, float), np.array([c for p in dst for c in p], float))
    return np.append(h, 1).reshape(3, 3)


_SCREEN = [(0, 0), (W, 0), (W, H), (0, H)]
_H_OUT_TO_FLAT = _homography(_SCREEN, QUAD)
_H_FLAT_TO_OUT = np.linalg.inv(_H_OUT_TO_FLAT)
_PERSPECTIVE = tuple((_H_OUT_TO_FLAT / _H_OUT_TO_FLAT[2, 2]).flatten()[:8])


def _flat_to_screen(x: float, y: float) -> tuple[float, float]:
    u, v, w = _H_FLAT_TO_OUT @ np.array([x, y, 1.0])
    return u / w, v / w


def _ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------------------
# Text sprites
# ---------------------------------------------------------------------------
def _font(path: Path, size: int):
    try:
        return ImageFont.truetype(str(path), size, layout_engine=ImageFont.Layout.RAQM)
    except Exception:
        return ImageFont.truetype(str(path), size)


def _text_block(text: str, path: Path, size: int, fill, *, max_w: int, max_lines: int,
                stroke: int = 0, align: str = "left", min_size: int = 28) -> Image.Image | None:
    text = _clean(text)
    if not text:
        return None
    probe = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    while True:
        font = _font(path, size)
        lines, hard = [], False
        for raw in text.split("\n"):
            wrapped, broke = _wrap_ex(raw, font, max_w, probe)
            lines += wrapped
            hard = hard or broke
        if (len(lines) <= max_lines and not hard) or size <= min_size:
            break
        size -= 4
    lh = int(size * 1.32)
    widths = [probe.textlength(ln, font=font) for ln in lines]
    img = Image.new("RGBA", (int(max(widths)) + stroke * 2 + 8, lh * len(lines) + stroke * 2 + int(size * 0.35)))
    d = ImageDraw.Draw(img)
    for i, (ln, w) in enumerate(zip(lines, widths)):
        x = stroke + 4 + ((img.width - 8 - stroke * 2 - w) / 2 if align == "center" else 0)
        d.text((x, stroke + i * lh), ln, font=font, fill=fill, stroke_width=stroke,
               stroke_fill=(0, 0, 0, 230) if stroke else None)
    return img


def _card_sprite(title: str, subtitle: str, fact: str, *, hook: bool) -> Image.Image:
    """Bold title block + subtitle + fact line, laid out top-left."""
    parts = []
    t = _text_block(title, FONT_DISPLAY_PATH, 128 if hook else 104, (255, 255, 255, 255),
                    max_w=900, max_lines=2)
    if t:
        pad_x, pad_y = 34, 14
        block = Image.new("RGBA", (t.width + pad_x * 2, t.height + pad_y * 2), CRIMSON + (255,))
        block.alpha_composite(t, (pad_x, pad_y))
        parts.append((block, 0))
    s = _text_block(subtitle, FONT_DISPLAY_MEDIUM_PATH, 56 if hook else 50, (255, 255, 255, 255),
                    max_w=950, max_lines=2, stroke=5)
    if s:
        parts.append((s, 18))
    f = _text_block(fact, FONT_DISPLAY_MEDIUM_PATH, 42, GOLD + (255,), max_w=950, max_lines=1, stroke=4)
    if f:
        parts.append((f, 6))
    if not parts:
        return Image.new("RGBA", (1, 1))
    width = max(p.width for p, _ in parts)
    height = sum(p.height + gap for p, gap in parts)
    card = Image.new("RGBA", (width, height))
    y = 0
    for p, gap in parts:
        y += gap
        card.alpha_composite(p, (0, y))
        y += p.height
    return card


def _label_sprite(text: str) -> Image.Image:
    t = _text_block(text, FONT_DISPLAY_MEDIUM_PATH, 40, (255, 255, 255, 255), max_w=420,
                    max_lines=1, stroke=4) or Image.new("RGBA", (1, 1))
    img = Image.new("RGBA", (t.width + 26, max(t.height, 26)))
    d = ImageDraw.Draw(img)
    cy = img.height // 2 - 4
    d.ellipse((2, cy - 8, 18, cy + 8), fill=(255, 255, 255, 255), outline=(0, 0, 0, 200), width=3)
    img.alpha_composite(t, (24, 0))
    return img


def _pin_sprite(number: str) -> Image.Image:
    label = number or "•"
    t = _text_block(label, FONT_DISPLAY_PATH, 52, (20, 20, 20, 255), max_w=200, max_lines=1)
    side = max(76, (t.width if t else 0) + 28)
    img = Image.new("RGBA", (side + 8, side + 22))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((4, 4, side + 4, side + 4), radius=14, fill=GOLD + (255,), outline=(20, 20, 20, 255), width=4)
    d.polygon([(side / 2 - 8, side + 2), (side / 2 + 16, side + 2), (side / 2 + 4, side + 20)], fill=(20, 20, 20, 255))
    if t:
        img.alpha_composite(t, (int(4 + (side - t.width) / 2), int(4 + (side - t.height) / 2 + 2)))
    return img


def _subtitle_chunks(text: str, max_chars: int = 34) -> list[str]:
    words: list[str] = []
    for w in _clean(text).split(" "):
        while len(w) > max_chars:  # long unspaced Thai run: cut between clusters
            piece, rest = "", _clusters(w)
            while rest and len(piece) + len(rest[0]) <= max_chars - 6:
                piece += rest.pop(0)
            words.append(piece)
            w = "".join(rest)
        words.append(w)
    chunks, cur = [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > max_chars:
            chunks.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        chunks.append(cur)
    return chunks or [""]


def _subtitle_sprite(text: str) -> Image.Image | None:
    return _text_block(text, FONT_DISPLAY_MEDIUM_PATH, 54, (255, 255, 255, 255), max_w=960,
                       max_lines=2, stroke=6, align="center")


def _gradients() -> Image.Image:
    g = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(g)
    for y in range(0, 620):
        d.line([(0, y), (W, y)], fill=(0, 0, 0, int(150 * (1 - y / 620) ** 1.4)))
    for y in range(H - 700, H):
        t = (y - (H - 700)) / 700
        d.line([(0, y), (W, y)], fill=(0, 0, 0, int(170 * t ** 1.6)))
    return g


# ---------------------------------------------------------------------------
# Geography for each beat
# ---------------------------------------------------------------------------
@dataclass
class Overlay:
    style: str                                   # line | area | pin
    lines: list[np.ndarray] = field(default_factory=list)   # arrays of (lon, lat)
    polygons: list[np.ndarray] = field(default_factory=list)
    point: tuple[float, float] | None = None
    number: str = ""
    primary: bool = False


@dataclass
class GeoBeat:
    overlays: list[Overlay]
    labels: list[tuple[str, float, float]]
    target: tuple[float, float] | None
    extent_km: float | None = None


def _valid_region(region: dict) -> tuple[float, float, float, float] | None:
    try:
        w, s, e, n = (float(region[k]) for k in ("west", "south", "east", "north"))
    except (KeyError, TypeError, ValueError):
        return None
    if not (w < e and s < n and -180 <= w and e <= 180 and -85 <= s and n <= 85):
        return None
    return w, s, e, n


def _pad_bbox(b, frac=0.35):
    w, s, e, n = b
    dx, dy = (e - w) * frac + 0.05, (n - s) * frac + 0.05
    return w - dx, s - dy, e + dx, n + dy


def resolve_geography(plan) -> tuple[list[GeoBeat], tuple[float, float, float, float]]:
    region = _valid_region(plan.region or {}) or THAILAND
    search = _pad_bbox(region)
    beats: list[GeoBeat] = []
    for sc in plan.scenes:
        overlays: list[Overlay] = []
        pts: list[tuple[float, float]] = []
        for i, f in enumerate(sc.focus or []):
            name, kind, style = f.get("name", ""), f.get("kind", "place"), f.get("style", "pin")
            ov = Overlay(style=style, number=str(f.get("number", "") or ""), primary=(i == 0))
            feat = None if kind == "place" else maps.fetch_feature(name, kind, search)
            if feat:
                ov.lines = [np.array(x) for x in feat.lines]
                ov.polygons = [np.array(x) for x in feat.polygons]
                if style == "pin" or (style == "area" and not ov.polygons):
                    lon0, lat0, lon1, lat1 = feat.bbox()
                    ov.point = ((lon0 + lon1) / 2, (lat0 + lat1) / 2)
                    ov.style = "pin" if style == "pin" else "line"
                pts += feat.points
            else:
                p = maps.geocode(name, region)
                if not p:
                    print(f"    [map] not found: {name} ({kind})")
                    continue
                ov.point, ov.style = p, "pin"
                pts.append(p)
            overlays.append(ov)
        labels = []
        for name in sc.labels or []:
            p = maps.geocode(name, region)
            if p:
                labels.append((name, p[0], p[1]))
        target, extent = None, None
        focus_pts = pts or [(lon, lat) for _, lon, lat in labels]
        if focus_pts:
            lons, lats = [p[0] for p in focus_pts], [p[1] for p in focus_pts]
            target = ((min(lons) + max(lons)) / 2, (min(lats) + max(lats)) / 2)
            lat_mid = target[1]
            extent = max((max(lons) - min(lons)) * 111 * math.cos(math.radians(lat_mid)),
                         (max(lats) - min(lats)) * 111)
        beats.append(GeoBeat(overlays, labels, target, extent))
    return beats, region


# ---------------------------------------------------------------------------
# Map frames
# ---------------------------------------------------------------------------
class MapCamera:
    """Mosaics (two zoom levels) + a camera path for one beat."""

    def __init__(self, lat_ref: float, path: list[tuple[float, float, float]]):
        self.lat = lat_ref
        self.path = path  # [(lon, lat, span_km)] sampled along the beat
        spans = [p[2] for p in path]
        z_hi = self._z(min(spans))
        z_lo = self._z(max(spans))
        self.levels: dict[int, maps.Mosaic] = {}
        for z in sorted({z_hi, z_lo}):
            m = self._mosaic_for(z, path)  # each level covers the whole camera path
            self.levels[m.z] = m

    def _z(self, span_km: float) -> int:
        m_per_flat_px = span_km * 1000 / MID_FLAT_W
        z = math.log2(156543.03392 * math.cos(math.radians(self.lat)) / m_per_flat_px)
        return max(3, min(maps.MAX_TILE_Z, math.ceil(z - 0.15)))

    def _view_bbox(self, lon, lat, span_km):
        half_w = span_km / MID_FLAT_W * FW / 2 / (111 * math.cos(math.radians(lat)))
        half_h = span_km / MID_FLAT_W * FH / 2 / 111
        return lon - half_w, lat - half_h, lon + half_w, lat + half_h

    def _mosaic_for(self, z, path):
        boxes = [self._view_bbox(*p) for p in path]
        w, s = min(b[0] for b in boxes), min(b[1] for b in boxes)
        e, n = max(b[2] for b in boxes), max(b[3] for b in boxes)
        while True:
            try:
                return maps.build_mosaic(w, s, e, n, z)
            except ValueError:
                z -= 1  # too many tiles at this zoom → coarser imagery

    def frame(self, lon: float, lat: float, span_km: float):
        z = self._z(span_km)
        mosaic = self.levels[min(self.levels, key=lambda k: (abs(k - z), -k))]
        mpp = maps.meters_per_px(self.lat, mosaic.z)
        crop_w = FW * span_km * 1000 / (MID_FLAT_W * mpp)
        crop_h = crop_w * FH / FW
        cx, cy = mosaic.px(lon, lat)
        x0, y0 = cx - crop_w / 2, cy - crop_h / 2
        flat = mosaic.image.transform((FW, FH), Image.EXTENT, (x0, y0, x0 + crop_w, y0 + crop_h),
                                      Image.BILINEAR)
        scale = FW / crop_w

        def to_flat(arr: np.ndarray) -> np.ndarray:
            n = 256 * 2 ** mosaic.z
            x = (arr[:, 0] + 180.0) / 360.0 * n - mosaic.origin[0]
            s = np.sin(np.radians(np.clip(arr[:, 1], -85, 85)))
            y = (0.5 - np.log((1 + s) / (1 - s)) / (4 * np.pi)) * n - mosaic.origin[1]
            return np.stack([(x - x0) * scale, (y - y0) * scale], axis=1)

        return flat, to_flat


def _draw_lines(layer: ImageDraw.ImageDraw, pts: np.ndarray, color, reveal: float, strength: float):
    if len(pts) < 2:
        return
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    total = seg.sum()
    if total < 2:
        return
    if reveal < 1:
        keep_len, acc, out = total * reveal, 0.0, [pts[0]]
        for i, L in enumerate(seg):
            if acc + L >= keep_len:
                frac = (keep_len - acc) / L if L else 0
                out.append(pts[i] + (pts[i + 1] - pts[i]) * frac)
                break
            acc += L
            out.append(pts[i + 1])
        pts = np.array(out)
    xy = [tuple(p) for p in pts]
    a = strength
    layer.line(xy, fill=color + (int(60 * a),), width=40, joint="curve")
    layer.line(xy, fill=color + (int(140 * a),), width=20, joint="curve")
    layer.line(xy, fill=color + (int(255 * a),), width=9, joint="curve")
    if a > 0.9:
        layer.line(xy, fill=(255, 255, 255, 230), width=3, joint="curve")


def _render_map_overlays(flat: Image.Image, to_flat, beat: GeoBeat, t: float,
                         context: list[Overlay]) -> Image.Image:
    layer = Image.new("RGBA", (FW, FH))
    d = ImageDraw.Draw(layer)
    for ov in context:  # earlier beats' main lines stay as faint context
        for ln in ov.lines:
            _draw_lines(d, to_flat(ln), CYAN, 1.0, 0.45)
    for k, ov in enumerate(beat.overlays):
        color = CYAN if ov.primary else RED_LINE
        if ov.style == "area" and ov.polygons:
            alpha = _ease(t / 0.35)
            for poly in ov.polygons:
                xy = [tuple(p) for p in to_flat(poly)]
                if len(xy) > 2:
                    d.polygon(xy, fill=AREA + (int(105 * alpha),), outline=AREA + (int(255 * alpha),), width=5)
        elif ov.style == "line":
            reveal = _ease((t - 0.08 - 0.1 * k) / 0.55)
            for ln in ov.lines:
                _draw_lines(d, to_flat(ln), color, reveal, 1.0)
    out = flat.convert("RGBA")
    out.alpha_composite(layer)
    return out


# ---------------------------------------------------------------------------
# Archival look + year cards
# ---------------------------------------------------------------------------
def _vignette() -> Image.Image:
    yy, xx = np.mgrid[0:H, 0:W]
    d = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    alpha = (np.clip((d - 0.55) / 0.85, 0, 1) ** 1.6 * 175).astype(np.uint8)
    v = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    v.putalpha(Image.fromarray(alpha, "L"))
    return v


def _grain(seed: int) -> Image.Image:
    rng = np.random.default_rng(seed)
    noise = rng.integers(0, 255, (H // 2, W // 2), dtype=np.uint8)
    g = Image.fromarray(noise, "L").resize((W, H), Image.NEAREST)
    layer = Image.new("RGBA", (W, H), (128, 128, 128, 0))
    layer.putalpha(g.point(lambda v: 16 if v > 170 else 0))
    return layer


_VIGNETTE: Image.Image | None = None
_GRAINS: list[Image.Image] = []


def _archival(img: Image.Image, f: int) -> Image.Image:
    global _VIGNETTE
    if _VIGNETTE is None:
        _VIGNETTE = _vignette()
        _GRAINS.extend(_grain(k) for k in range(4))
    out = img.convert("RGBA")
    out.alpha_composite(_VIGNETTE)
    out.alpha_composite(_GRAINS[(f // 2) % len(_GRAINS)])
    return out


def _year_background(photo: Image.Image | None) -> Image.Image:
    from PIL import ImageEnhance, ImageFilter
    if photo is not None:
        bg = photo.resize((W // 4, H // 4)).filter(ImageFilter.GaussianBlur(6)).resize((W, H))
        return ImageEnhance.Brightness(bg).enhance(0.32).convert("RGB")
    bg = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(bg)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=(int(24 - 14 * t), int(20 - 12 * t), int(28 - 16 * t)))
    return bg


def _year_frame(bg: Image.Image, f: int, n: int, year_from: float, year_to: float,
                date: str, subtitle: str, fact: str) -> Image.Image:
    t = f / max(n - 1, 1)
    z = 1.0 + 0.06 * _ease(t)
    w2, h2 = W / z, H / z
    frame = bg.transform((W, H), Image.EXTENT, ((W - w2) / 2, (H - h2) / 2, (W + w2) / 2, (H + h2) / 2),
                         Image.BILINEAR).convert("RGBA")
    k = 1 - (1 - min(t / 0.45, 1)) ** 3          # ease-out count-up
    shown = int(round(year_from + (year_to - year_from) * k))
    d = ImageDraw.Draw(frame)
    # timeline with a travelling marker
    x0, x1, ty = 110, W - 110, 1035
    d.line([(x0, ty), (x1, ty)], fill=GOLD + (120,), width=4)
    for i in range(9):
        x = x0 + (x1 - x0) * i / 8
        d.line([(x, ty - 14), (x, ty + 14)], fill=GOLD + (110,), width=3)
    mx = x0 + (x1 - x0) * (0.15 + 0.7 * k)
    d.ellipse((mx - 16, ty - 16, mx + 16, ty + 16), fill=GOLD + (255,), outline=(20, 20, 20, 255), width=4)
    era = _text_block("พ.ศ.", FONT_DISPLAY_MEDIUM_PATH, 58, (255, 255, 255, 220), max_w=400, max_lines=1, stroke=3)
    num = _text_block(str(shown), FONT_DISPLAY_PATH, 250, GOLD + (255,), max_w=1000, max_lines=1, stroke=6)
    if era:
        frame.alpha_composite(era, ((W - era.width) // 2, 540))
    if num:
        frame.alpha_composite(num, ((W - num.width) // 2, 600))
    # date, event and fact stack under the timeline, fading in once the counter lands
    a = int(255 * _ease((t - 0.3) / 0.15))
    y = 1078
    for text, font, size, fill, lines in ((date, FONT_DISPLAY_PATH, 70, (255, 255, 255), 1),
                                          (subtitle, FONT_DISPLAY_MEDIUM_PATH, 52, (255, 255, 255), 2),
                                          (fact, FONT_DISPLAY_MEDIUM_PATH, 44, GOLD, 1)):
        block = _text_block(text, font, size, fill + (255,), max_w=940, max_lines=lines, stroke=4, align="center")
        if block and a > 0:
            if a < 255:
                block = Image.blend(Image.new("RGBA", block.size), block, a / 255)
            frame.alpha_composite(block, ((W - block.width) // 2, y))
        y += (block.height + 4) if block else 0
    return frame


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------
MAX_MB = 44  # Telegram bots reject uploads over 50 MB


class _Writer:
    def __init__(self, path: Path, seconds: float):
        # Bitrate sized so the whole file (video + 160k audio) stays under MAX_MB.
        kbps = max(1500, min(8000, int(MAX_MB * 8 * 1024 / max(seconds, 1) - 200)))
        self.proc = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
             "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
             "-b:v", f"{kbps}k", "-maxrate", f"{int(kbps * 1.15)}k", "-bufsize", f"{kbps * 2}k",
             "-pix_fmt", "yuv420p", str(path)],
            stdin=subprocess.PIPE)
        self.last: Image.Image | None = None

    def write(self, img: Image.Image):
        self.proc.stdin.write(img.convert("RGB").tobytes())
        self.last = img

    def close(self):
        self.proc.stdin.close()
        if self.proc.wait() != 0:
            raise RuntimeError("ffmpeg failed while encoding frames")


def _place(canvas: Image.Image, sprite: Image.Image | None, x: float, y: float):
    if sprite is not None:
        canvas.alpha_composite(sprite, (int(x), int(y)))


def _overlay_screen(frame: Image.Image, *, card, card_t: int, sub, credit, labels=(), pins=()) -> Image.Image:
    canvas = frame.convert("RGBA")
    canvas.alpha_composite(_GRADIENTS)
    for sprite, (x, y) in labels:
        _place(canvas, sprite, x, y)
    for sprite, (x, y) in pins:
        _place(canvas, sprite, x, y)
    if card is not None:
        k = _ease(card_t / CARD_IN)
        c = card if k >= 1 else Image.blend(Image.new("RGBA", card.size), card, k)
        _place(canvas, c, 56 - (1 - k) * 60, 150)
    if sub is not None:
        _place(canvas, sub, (W - sub.width) / 2, 1395)
    _place(canvas, credit, 40, H - 70)
    return canvas


_GRADIENTS = _gradients()


def render(plan, beat_durs: list[float], voice: Path, run_dir: Path, out_name: str,
           photo_images: dict[int, object] | None = None) -> Path:
    """Render the whole story; returns the final MP4 path."""
    from ..frames import prepare_frame

    run_dir.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    geo, region = resolve_geography(plan)
    lat_ref = (region[1] + region[3]) / 2
    region_center = ((region[0] + region[2]) / 2, lat_ref)
    photo_images = photo_images or {}

    credit_map = _text_block(maps.BASEMAP_CREDIT, FONT_PATH, 22, (255, 255, 255, 190), max_w=1000,
                             max_lines=1, min_size=16)
    silent = run_dir / "story_silent.mp4"
    writer = _Writer(silent, sum(beat_durs))
    cam_lon, cam_lat, cam_span = None, None, None
    context: list[Overlay] = []
    label_cache: dict[str, Image.Image] = {}
    prev_kind = None
    last_photo: Image.Image | None = None
    last_year = 0.0

    for i, (sc, d) in enumerate(zip(plan.scenes, beat_durs)):
        n = max(int(round(d * FPS)), 1)
        hook = i == 0
        card = _card_sprite(plan.hook_title or sc.card_title if hook else sc.card_title,
                            plan.hook_subtitle or sc.card_subtitle if hook else sc.card_subtitle,
                            sc.card_fact, hook=hook)
        chunks = _subtitle_chunks(sc.narration)
        weights = [max(len(c), 1) for c in chunks]
        bounds = np.cumsum(weights) / sum(weights) * n
        subs = [_subtitle_sprite(c) for c in chunks]
        g = geo[i]
        is_photo = sc.visual == "photo" and i in photo_images
        # a photo beat with no usable archival photo becomes a designed card, never a fake image
        kind = "photo" if is_photo else ("card" if sc.visual in ("year", "photo") else "map")
        print(f"    [render] beat {i + 1}/{len(plan.scenes)} {sc.visual if kind == 'card' else kind} {d:.1f}s")

        if kind == "card":
            bg_photo = last_photo or next((Image.open(prepare_frame(photo_images[j].path, run_dir / f"photo_{j}.jpg")).convert("RGB")
                                           for j in range(i + 1, len(plan.scenes)) if j in photo_images), None)
            bg = _year_background(bg_photo)
            y_to = float(sc.year or 0) if sc.visual == "year" else 0.0
            y_from = y_to if last_year == y_to else (last_year if 0 < last_year < y_to else y_to - 12)
            for f in range(n):
                sub = subs[min(int(np.searchsorted(bounds, f, side="right")), len(subs) - 1)]
                if y_to:
                    fr = _year_frame(bg, f, n, y_from, y_to, sc.card_title, sc.card_subtitle, sc.card_fact)
                else:
                    t = f / max(n - 1, 1)
                    z = 1.0 + 0.06 * _ease(t)
                    w2, h2 = W / z, H / z
                    fr = bg.transform((W, H), Image.EXTENT, ((W - w2) / 2, (H - h2) / 2, (W + w2) / 2, (H + h2) / 2),
                                      Image.BILINEAR)
                out = _overlay_screen(_archival(fr, f), card=None if y_to and not hook else card, card_t=f,
                                      sub=sub, credit=None)
                if prev_kind and prev_kind != kind and f < CROSSFADE and writer.last is not None:
                    out = Image.blend(writer.last.convert("RGBA"), out, (f + 1) / CROSSFADE)
                writer.write(out)
            last_year = y_to or last_year
            prev_kind = kind
            continue

        if is_photo:
            img = photo_images[i]
            framed = Image.open(prepare_frame(img.path, run_dir / f"photo_{i}.jpg")).convert("RGB")
            last_photo = framed
            credit = _text_block(img.credit, FONT_PATH, 22, (255, 255, 255, 190), max_w=1000,
                                 max_lines=1, min_size=16)
            for f in range(n):
                t = f / max(n - 1, 1)
                z = 1.0 + 0.10 * _ease(t)
                w2, h2 = W / z, H / z
                x0, y0 = (W - w2) / 2, (H - h2) / 2 - 20 * _ease(t)
                fr = framed.transform((W, H), Image.EXTENT, (x0, y0, x0 + w2, y0 + h2), Image.BILINEAR)
                sub = subs[min(int(np.searchsorted(bounds, f, side="right")), len(subs) - 1)]
                out = _overlay_screen(_archival(fr, f), card=card, card_t=f, sub=sub, credit=credit)
                if prev_kind and prev_kind != kind and f < CROSSFADE and writer.last is not None:
                    out = Image.blend(writer.last.convert("RGBA"), out, (f + 1) / CROSSFADE)
                writer.write(out)
            prev_kind = kind
            continue

        target = g.target or (cam_lon, cam_lat) if cam_lon is not None else g.target or region_center
        target = target or region_center
        span1 = float(sc.span_end_km)
        if g.extent_km and span1 < g.extent_km * 0.35:
            span1 = max(span1, g.extent_km * 0.35)  # keep the subject on screen
        if cam_lon is None or prev_kind == "photo":
            start = (target[0], target[1], float(sc.span_start_km))
        else:
            start = (cam_lon, cam_lat, cam_span)
        end = (target[0], target[1], span1)
        if abs(start[2] - end[2]) / end[2] < 0.05 and abs(start[0] - end[0]) + abs(start[1] - end[1]) < 1e-4:
            end = (end[0], end[1], end[2] * 0.9)  # never hold a dead-still frame

        def at(t):
            e = _ease(t)
            span = math.exp(math.log(start[2]) + (math.log(end[2]) - math.log(start[2])) * e)
            return start[0] + (end[0] - start[0]) * e, start[1] + (end[1] - start[1]) * e, span

        camera = MapCamera(lat_ref, [at(k / 6) for k in range(7)])
        label_sprites = [(label_cache.setdefault(name, _label_sprite(name)), lon, lat) for name, lon, lat in g.labels]
        pin_overlays = [ov for ov in g.overlays if ov.style == "pin" and ov.point]
        pin_sprites = [_pin_sprite(ov.number) for ov in pin_overlays]

        for f in range(n):
            t = f / max(n - 1, 1)
            lon, lat, span = at(t)
            flat, to_flat = camera.frame(lon, lat, span)
            flat = _render_map_overlays(flat, to_flat, g, t, context)
            screen = flat.convert("RGB").transform((W, H), Image.PERSPECTIVE, _PERSPECTIVE, Image.BILINEAR)

            placed_labels, boxes = [], []
            for sprite, llon, llat in label_sprites:
                fx, fy = to_flat(np.array([[llon, llat]]))[0]
                sx, sy = _flat_to_screen(fx, fy)
                x0, y0 = sx - 10, sy - sprite.height / 2
                box = (x0, y0, x0 + sprite.width, y0 + sprite.height)
                if box[0] < 16 or box[2] > W - 16 or not 560 < sy < 1330:
                    continue
                if any(not (box[2] < b[0] or box[0] > b[2] or box[3] < b[1] or box[1] > b[3]) for b in boxes):
                    continue
                boxes.append(box)
                placed_labels.append((sprite, (x0, y0)))
            placed_pins = []
            pin_k = _ease((t - 0.2) / 0.2)
            if pin_k > 0:
                for ov, sprite in zip(pin_overlays, pin_sprites):
                    fx, fy = to_flat(np.array([ov.point]))[0]
                    sx, sy = _flat_to_screen(fx, fy)
                    if 0 < sx < W and 400 < sy < 1380:
                        s = sprite if pin_k >= 1 else Image.blend(Image.new("RGBA", sprite.size), sprite, pin_k)
                        placed_pins.append((s, (sx - sprite.width / 2, sy - sprite.height)))
            sub = subs[min(int(np.searchsorted(bounds, f, side="right")), len(subs) - 1)]
            out = _overlay_screen(screen, card=card, card_t=f, sub=sub, credit=credit_map,
                                  labels=placed_labels, pins=placed_pins)
            if prev_kind and prev_kind != kind and f < CROSSFADE and writer.last is not None:
                out = Image.blend(writer.last.convert("RGBA"), out, (f + 1) / CROSSFADE)
            writer.write(out)

        cam_lon, cam_lat, cam_span = end
        context += [ov for ov in g.overlays if ov.primary and ov.lines][:1]
        context = context[-2:]
        prev_kind = kind

    writer.close()
    return _mix(silent, voice, beat_durs, OUTPUT_DIR / out_name, run_dir)


# ---------------------------------------------------------------------------
# Soundtrack
# ---------------------------------------------------------------------------
def _whoosh(run_dir: Path) -> Path:
    path = ASSETS / "sfx" / "whoosh.wav"
    if path.exists():
        return path
    path = run_dir / "whoosh.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    "anoisesrc=color=pink:duration=0.7:amplitude=0.6",
                    "-af", "highpass=f=300,lowpass=f=5000,afade=t=in:d=0.35,afade=t=out:st=0.35:d=0.35,volume=0.6",
                    str(path)], check=True)
    return path


def _music() -> Path | None:
    folder = MUSIC_DIR / "story"
    chosen = folder / STORY_MUSIC
    if chosen.exists():
        return chosen
    tracks = sorted(folder.glob("*.mp3")) if folder.exists() else []
    preferred = [t for t in tracks if not t.name.startswith("ambient_pad")]
    return (preferred or tracks or [None])[0]


def _mix(silent: Path, voice: Path, beat_durs: list[float], final: Path, run_dir: Path) -> Path:
    total = sum(beat_durs)
    music = _music()
    whoosh = _whoosh(run_dir)
    starts = list(np.cumsum([0] + beat_durs[:-1]))[1:]
    inputs = ["-i", str(silent), "-i", str(voice)]
    graph = ["[1:a]aresample=44100,apad[vo]"]
    mix = ["[vo]"]
    idx = 2
    if music:
        inputs += ["-stream_loop", "-1", "-i", str(music)]
        graph.append(f"[{idx}:a]aresample=44100,volume=0.55,afade=t=in:d=1.5,"
                     f"afade=t=out:st={max(total - 2, 0):.2f}:d=2[mraw]")
        graph.append("[vo]asplit=2[vo1][vosc]")
        graph.append("[mraw][vosc]sidechaincompress=threshold=0.02:ratio=10:attack=15:release=450[mduck]")
        mix = ["[vo1]", "[mduck]"]
        idx += 1
    for k, s in enumerate(starts):
        inputs += ["-i", str(whoosh)]
        ms = max(int((s - 0.3) * 1000), 0)
        graph.append(f"[{idx}:a]aresample=44100,adelay={ms}:all=1,volume=0.35[w{k}]")
        mix.append(f"[w{k}]")
        idx += 1
    graph.append(f"{''.join(mix)}amix=inputs={len(mix)}:duration=longest:normalize=0,"
                 "loudnorm=I=-15:TP=-1.5:LRA=11[a]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(graph),
                    "-map", "0:v", "-map", "[a]", "-t", f"{total:.3f}", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(final)], check=True)
    print(f"  [render] final -> {final} ({total:.1f}s)")
    return final
