"""
FFmpeg compositor — turns scenes + clips + voiceover into a finished 9:16 MP4.

Strategy (robust, debuggable): render each scene to its own normalized silent
clip, concatenate them, then lay the Thai voiceover (and optional ducked music)
over the top.

Scene kinds:
  ai        : the fal.ai motion clip, cropped to 1080x1920, caption overlaid
  kenburns  : slow zoom/pan on the product image, caption overlaid
  cta       : solid Shopee-orange card with stacked centered text

Captions use the Sarabun font (full Thai glyph coverage) and are passed via
textfile= so Thai/Unicode never breaks shell escaping.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .captions import render_caption
from .config import FPS, OUTPUT_DIR, VIDEO_H, VIDEO_W, WORK_DIR
from .voiceover import audio_duration


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{' '.join(cmd)}\n\n{proc.stderr[-1500:]}")


def _caption_png(caption: str, tag: str, *, big: bool = False, position: str = "lower") -> Path | None:
    if not caption or not caption.strip():
        return None
    png = WORK_DIR / f"cap_{tag}.png"
    return render_caption(caption, png, big=big, position=position)


def _render_ai(clip: Path, dur: float, caption: str, tag: str, out: Path) -> None:
    cap = _caption_png(caption, tag)
    base_vf = (
        f"scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=increase,"
        f"crop={VIDEO_W}:{VIDEO_H},fps={FPS}"
    )
    if cap:
        _run([
            "ffmpeg", "-y", "-stream_loop", "-1", "-i", str(clip), "-i", str(cap),
            "-t", f"{dur:.3f}",
            "-filter_complex", f"[0:v]{base_vf}[v];[v][1:v]overlay=0:0[o]",
            "-map", "[o]", "-an",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS), str(out),
        ])
    else:
        _run([
            "ffmpeg", "-y", "-stream_loop", "-1", "-i", str(clip),
            "-t", f"{dur:.3f}", "-vf", base_vf, "-an",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS), str(out),
        ])


def _render_kenburns(image: Path, dur: float, caption: str, tag: str, out: Path) -> None:
    frames = max(int(dur * FPS), 1)
    cap = _caption_png(caption, tag)
    kb = (
        f"[0:v]scale={VIDEO_W*2}:{VIDEO_H*2}:force_original_aspect_ratio=increase,"
        f"crop={VIDEO_W*2}:{VIDEO_H*2},"
        f"zoompan=z='min(zoom+0.0012,1.3)':d={frames}:"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={VIDEO_W}x{VIDEO_H}:fps={FPS}"
    )
    if cap:
        _run([
            "ffmpeg", "-y", "-loop", "1", "-i", str(image), "-i", str(cap),
            "-t", f"{dur:.3f}",
            "-filter_complex", f"{kb}[v];[v][1:v]overlay=0:0[o]",
            "-map", "[o]", "-an",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS), str(out),
        ])
    else:
        _run([
            "ffmpeg", "-y", "-loop", "1", "-i", str(image),
            "-t", f"{dur:.3f}", "-filter_complex", f"{kb}[o]", "-map", "[o]", "-an",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS), str(out),
        ])


def _render_cta(bg_color: str, dur: float, caption: str, tag: str, out: Path) -> None:
    color = bg_color.lstrip("#")
    cap = _caption_png(caption, tag, big=True, position="center")
    if cap:
        _run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c=0x{color}:s={VIDEO_W}x{VIDEO_H}:d={dur:.3f}:r={FPS}",
            "-i", str(cap),
            "-filter_complex", "[0:v][1:v]overlay=0:0[o]", "-map", "[o]", "-an",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS), str(out),
        ])
    else:
        _run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", f"color=c=0x{color}:s={VIDEO_W}x{VIDEO_H}:d={dur:.3f}:r={FPS}", "-an",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS), str(out),
        ])


def _scaled_durations(plan, voice_dur: float) -> list[float]:
    """
    AI clips keep their generated length; the remaining time (to cover the
    voiceover + 2s tail) is distributed across the non-AI scenes.
    """
    fixed = sum(s.duration for s in plan.scenes if s.kind == "ai")
    flex_scenes = [s for s in plan.scenes if s.kind != "ai"]
    flex_default = sum(s.duration for s in flex_scenes) or 1.0
    target_total = max(voice_dur + 2.0, fixed + flex_default)
    flex_budget = max(target_total - fixed, len(flex_scenes) * 3.0)

    durs = []
    for s in plan.scenes:
        if s.kind == "ai":
            durs.append(s.duration)
        else:
            share = (s.duration / flex_default) * flex_budget
            durs.append(max(share, 3.0))
    return durs


def compose(plan, clips: dict[int, Path], voice: Path,
            music: Path | None = None, out_name: str = "video.mp4") -> Path:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    voice_dur = audio_duration(voice)
    durs = _scaled_durations(plan, voice_dur)
    total = sum(durs)

    # 1) render each scene
    scene_paths: list[Path] = []
    for i, (scene, dur) in enumerate(zip(plan.scenes, durs)):
        out = WORK_DIR / f"scene_{i}.mp4"
        tag = str(i)
        if scene.kind == "ai" and i in clips:
            _render_ai(clips[i], dur, scene.caption, tag, out)
        elif scene.kind == "kenburns" and scene.image_url:
            img = WORK_DIR / "product_src.jpg"
            if not img.exists():
                from .video_gen import download_image
                download_image(scene.image_url, img)
            _render_kenburns(img, dur, scene.caption, tag, out)
        else:  # cta or fallback
            _render_cta(scene.bg_color or "#EE4D2D", dur, scene.caption, tag, out)
        scene_paths.append(out)
        print(f"  [compose] scene {i} ({scene.kind}) -> {dur:.1f}s")

    # 2) concat
    concat_list = WORK_DIR / "concat.txt"
    concat_list.write_text("".join(f"file '{p.resolve()}'\n" for p in scene_paths))
    silent = WORK_DIR / "silent.mp4"
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
          "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS), str(silent)])

    # 3) audio: voice (padded with silence to full length) + optional ducked music.
    #    Padding guarantees the whole visual timeline (incl. CTA) survives; we cut
    #    to exactly `total` so there is no trailing dead air beyond the video.
    final = OUTPUT_DIR / out_name
    if music and music.exists():
        _run([
            "ffmpeg", "-y", "-i", str(silent), "-i", str(voice),
            "-stream_loop", "-1", "-i", str(music),
            "-filter_complex",
            f"[1:a]apad[vo];[2:a]volume=0.10[m];"
            f"[vo][m]amix=inputs=2:duration=longest:dropout_transition=0[a]",
            "-map", "0:v", "-map", "[a]", "-t", f"{total:.3f}",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(final),
        ])
    else:
        _run([
            "ffmpeg", "-y", "-i", str(silent), "-i", str(voice),
            "-filter_complex", "[1:a]apad[a]",
            "-map", "0:v", "-map", "[a]", "-t", f"{total:.3f}",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(final),
        ])
    print(f"  [compose] final -> {final} ({total:.1f}s)")
    return final


def first_music() -> Path | None:
    from .config import MUSIC_DIR
    if MUSIC_DIR.exists():
        for f in sorted(MUSIC_DIR.glob("*.mp3")):
            return f
    return None
