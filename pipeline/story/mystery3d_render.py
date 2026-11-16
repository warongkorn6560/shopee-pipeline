"""
Render a "mystery3d" episode: the Kling clip of each beat as the picture, with the series overlays on top
(hook title, evidence tags, clue counter, countdown, name plates, subtitles, fiction notice).

A clip shorter than its beat plays up to 1.5× slower, then holds its last frame; a beat without a clip
moves its keyframe still; the pause beat freezes the previous shot, darkened, under the countdown.
"""

from __future__ import annotations

import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from ..config import FONT_DISPLAY_MEDIUM_PATH, FONT_DISPLAY_PATH, FONT_PATH, FPS, OUTPUT_DIR, VIDEO_H, VIDEO_W
from ..voiceover import audio_duration
from .mystery import FICTION
from .mystery_render import AMBER, RED, _evidence_tag, _grain, _name_plate, _pill, _punch
from .render import _Writer, _ease, _mix, _scaled, _subtitle_chunks, _subtitle_sprite, _text_block

W, H = VIDEO_W, VIDEO_H
BLEND = 4                                   # frames of dissolve between beats (near-hard cuts)
MAX_SLOW = 1.5


def _clip_frames(path: Path, n: int):
    """n RGBA frames of the clip, cover-scaled to the canvas, slowed to fit (≤1.5×), then held."""
    factor = min(max(n / FPS / max(audio_duration(path), 0.1), 1.0), MAX_SLOW)
    vf = (f"setpts={factor:.4f}*PTS,fps={FPS},scale={W}:{H}:force_original_aspect_ratio=increase,"
          f"crop={W}:{H},tpad=stop_mode=clone:stop_duration=60")
    proc = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-i", str(path), "-vf", vf, "-frames:v", str(n),
                             "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    size, last = W * H * 3, None
    for _ in range(n):
        buf = proc.stdout.read(size)
        if len(buf) == size:
            last = Image.frombytes("RGB", (W, H), buf).convert("RGBA")
        yield last if last is not None else Image.new("RGBA", (W, H), (0, 0, 0, 255))
    proc.stdout.close()
    proc.wait()


def _still_frames(path: Path, n: int):
    """A keyframe with a slow push-in (used when its clip failed)."""
    img = Image.open(path).convert("RGBA")
    k = max(W / img.width, H / img.height)
    img = img.resize((math.ceil(img.width * k), math.ceil(img.height * k)), Image.LANCZOS)
    cx, cy = img.width / 2, img.height / 2
    for f in range(n):
        z = 1.0 + 0.08 * _ease(f / max(n - 1, 1))
        w2, h2 = W / z, H / z
        yield img.transform((W, H), Image.EXTENT, (cx - w2 / 2, cy - h2 / 2, cx + w2 / 2, cy + h2 / 2), Image.BICUBIC)


def _shade() -> Image.Image:
    """Dark gradients top and bottom so overlays read over any shot."""
    a = np.zeros((H, 1), dtype=np.float32)
    y = np.arange(H, dtype=np.float32)[:, None]
    a += np.clip((330 - y) / 330, 0, 1) * 150
    a += np.clip((y - (H - 640)) / 640, 0, 1) ** 1.4 * 215
    alpha = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8).repeat(W, axis=1), "L")
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.putalpha(alpha)
    return out


def render(plan, beat_durs: list[float], voice: Path, run_dir: Path, out_name: str,
           clips: dict[int, Path], stills: dict[int, Path]) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    silent = run_dir / "story_silent.mp4"
    writer = _Writer(silent, sum(beat_durs))
    shade = _shade()
    grain = [_grain(k) for k in range(4)]
    for g in grain:
        g.putalpha(g.split()[3].point(lambda v: v // 2))
    fiction = _pill("เรื่องแต่ง", 34, (255, 255, 255), (0, 0, 0, 150), outline=(255, 255, 255, 110))
    footer = _text_block(FICTION, FONT_PATH, 26, (220, 220, 220, 170), max_w=1000, max_lines=1, min_size=18)
    suspects = plan.suspects or [{"name": "?", "role": ""}]
    total_clues = max([s.clue for s in plan.scenes if s.visual == "clue"] or [0])
    shown: dict[int, tuple[str, str]] = {}
    pops: list[float] = []
    last_frame: Image.Image | None = None
    t0 = 0.0

    for i, (sc, d) in enumerate(zip(plan.scenes, beat_durs)):
        n = max(int(round(d * FPS)), 1)
        shot = sc.visual
        if shot == "pause" or (i not in clips and i not in stills):
            frozen = last_frame or Image.new("RGBA", (W, H), (8, 8, 12, 255))
            frozen = Image.blend(frozen.filter(ImageFilter.GaussianBlur(10)),
                                 Image.new("RGBA", (W, H), (0, 0, 0, 255)), 0.55)
            source = (frozen for _ in range(n))
        elif i in clips:
            source = _clip_frames(clips[i], n)
        else:
            source = _still_frames(stills[i], n)

        chunks = _subtitle_chunks(sc.narration)
        bounds = np.cumsum([max(len(c), 1) for c in chunks]) / sum(max(len(c), 1) for c in chunks) * n
        subs = [_subtitle_sprite(c) for c in chunks]
        punch = _punch(plan.hook_title or sc.punch) if i == 0 else (_punch(sc.punch) if sc.punch else None)
        hook_sub = (_text_block(plan.hook_subtitle, FONT_DISPLAY_MEDIUM_PATH, 58, AMBER + (255,), max_w=940,
                                max_lines=1, stroke=5, align="center") if i == 0 and plan.hook_subtitle else None)
        if shot == "clue" and sc.clue:
            shown[sc.clue] = (sc.card_title, sc.icon)
            pops.append(t0 + 0.25)
        tag = _evidence_tag(sc.clue, *shown[sc.clue]) if shot == "clue" and sc.clue in shown else None
        if tag is not None:
            tag = _scaled(tag, 0.72)
        small_tags = {k: _evidence_tag(k, *v, small=True) for k, v in sorted(shown.items())}
        counter = _pill(f"หลักฐาน {len(shown)}/{total_clues}", 36, AMBER, (0, 0, 0, 150)) if total_clues else None
        if shot == "pause":
            pops += [t0 + max(d - 3.2, 0.5) + k for k in range(3)]
        plates = []
        if shot == "suspects":
            plates = [_name_plate(s["name"], s["role"], sc.focus == k) for k, s in enumerate(suspects)]
        elif shot in ("reveal", "ending") and 0 <= plan.answer_suspect < len(suspects):
            s = suspects[plan.answer_suspect]
            plates = [_name_plate(s["name"], s["role"], True)]
        print(f"    [render] beat {i + 1}/{len(plan.scenes)} {shot} {d:.1f}s "
              f"({'clip' if i in clips else 'still' if i in stills else 'freeze'})")

        for f, raw in enumerate(source):
            frame = raw.copy()
            frame.alpha_composite(shade)
            if plates:                                                   # suspects stand left→right in order
                gap = W / (len(plates) + 1)
                for k, pl in enumerate(plates):
                    kk = _ease((f - k * 4) / 8)
                    if kk > 0:
                        x = gap * (k + 1) - pl.width / 2 if len(plates) > 1 else (W - pl.width) / 2
                        frame.alpha_composite(pl, (int(x), int(1400 + (1 - kk) * 60)))
            if tag is not None:                                          # evidence tag slides in, then holds
                kt = _ease(f / 9)
                frame.alpha_composite(tag, (int(W - tag.width - 30 + (1 - kt) * 600), 1080))
            if shot == "reveal" and small_tags:                          # the clues, strung back to the answer
                for k, st in small_tags.items():
                    lit = sc.clue == k
                    x = 40 + (k - 1) * 340
                    frame.alpha_composite(st if lit else Image.blend(Image.new("RGBA", st.size), st, 0.5), (x, 170))
                    if lit and f < 14:
                        ImageDraw.Draw(frame).rectangle((x - 6, 164, x + st.width + 6, 176 + st.height),
                                                        outline=RED + (255,), width=6)
            if shot == "pause":
                card = _text_block("หยุดดู! ทายก่อน", FONT_DISPLAY_PATH, 130, (255, 255, 255, 255), max_w=980,
                                   max_lines=2, align="center")
                frame.alpha_composite(card, ((W - card.width) // 2, 520))
                left = d - f / FPS
                num = str(max(1, min(3, math.ceil(left)))) if left <= 3.2 else "?"
                nk = 1 - (left % 1) if left <= 3.2 else 0
                big = _scaled(_text_block(num, FONT_DISPLAY_PATH, 330, RED + (255,), max_w=600, max_lines=1),
                              1.25 - 0.25 * _ease(nk * 3))
                frame.alpha_composite(big, ((W - big.width) // 2, 820))
                ask = _text_block("คอมเมนต์คำตอบไว้", FONT_DISPLAY_MEDIUM_PATH, 64, AMBER + (255,), max_w=900,
                                  max_lines=1, align="center")
                frame.alpha_composite(ask, ((W - ask.width) // 2, 1250))
            if punch is not None and shot != "pause":
                kp = min(f / 5, 1) if i == 0 else min(max(f - 2, 0) / 6, 1)   # the hook lands on frame one
                ps = _scaled(punch, 1.35 - 0.35 * _ease(kp)) if kp < 1 else punch
                y = 560 if i == 0 else (380 if tag is None else 330)
                frame.alpha_composite(ps, ((W - ps.width) // 2, y - ps.height // 2 + punch.height // 2))
                if hook_sub is not None and f >= 6:
                    frame.alpha_composite(hook_sub, ((W - hook_sub.width) // 2, y + punch.height + 10))
            frame.alpha_composite(grain[f % 4])
            frame.alpha_composite(fiction, (40, 70))
            if counter is not None and shown and shot != "pause":
                frame.alpha_composite(counter, (W - 40 - counter.width, 70))
            sub = subs[min(int(np.searchsorted(bounds, f, side="right")), len(subs) - 1)]
            if sub is not None:
                frame.alpha_composite(sub, ((W - sub.width) // 2, 1600))
            if footer is not None:
                frame.alpha_composite(footer, ((W - footer.width) // 2, H - 76))
            if i > 0 and f < BLEND and writer.last is not None:
                frame = Image.blend(writer.last.convert("RGBA"), frame, (f + 1) / (BLEND + 1))
            writer.write(frame)
            if shot != "pause":
                last_frame = raw
        t0 += d

    writer.close()
    return _mix(silent, voice, beat_durs, OUTPUT_DIR / out_name, run_dir, pops)
