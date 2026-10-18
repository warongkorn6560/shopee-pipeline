"""
FFmpeg compositor — turns scenes + clips + voiceover into a finished 9:16 MP4.

Each scene renders to its own normalized silent clip; the clips are
concatenated, then the voiceover (and optional ducked music) is laid on top.

Scene kinds:
  ai / story : a generated motion clip, cropped to 1080x1920, overlay on top
  kenburns   : slow zoom/pan over a still (product shot, map, photo, card)
  cta        : solid-color card with stacked centered text
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from .captions import render_overlay
from .config import FPS, OUTPUT_DIR, STORY_ACCENT, VIDEO_H, VIDEO_W, WORK_DIR
from .voiceover import audio_duration

_ENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
        "-pix_fmt", "yuv420p", "-r", str(FPS)]
MOTIONS = ("in", "pan-right", "out", "pan-left", "up", "in", "down", "out")


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{' '.join(cmd)}\n\n{proc.stderr[-1500:]}")


def _overlay_png(scene, tag: str, wd: Path, *, position: str = "lower") -> Path | None:
    if not any((scene.caption.strip(), scene.header, scene.badge, scene.credit)):
        return None
    png = wd / f"cap_{tag}.png"
    big = scene.big or scene.kind == "cta"
    return render_overlay(
        scene.caption, png, big=big,
        position="center" if (big or position == "center") else "lower",
        header=scene.header, badge=scene.badge, credit=scene.credit,
        accent=STORY_ACCENT, caption_y=0.74 if scene.header else 0.80,
    )


def _zoompan(motion: str, frames: int) -> str:
    n = max(frames, 1)
    zr, zp = 0.18, 1.15
    center_x, center_y = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    z, x, y = f"1+{zr}*on/{n}", center_x, center_y
    if motion == "out":
        z = f"1+{zr}*(1-on/{n})"
    elif motion == "pan-right":
        z, x = str(zp), f"(iw-iw/zoom)*on/{n}"
    elif motion == "pan-left":
        z, x = str(zp), f"(iw-iw/zoom)*(1-on/{n})"
    elif motion == "up":
        z, y = str(zp), f"(ih-ih/zoom)*(1-on/{n})"
    elif motion == "down":
        z, y = str(zp), f"(ih-ih/zoom)*on/{n}"
    return (f"scale={VIDEO_W * 2}:{VIDEO_H * 2},"
            f"zoompan=z='{z}':x='{x}':y='{y}':d={n}:s={VIDEO_W}x{VIDEO_H}:fps={FPS}")


def _render_kenburns(frame: Path, dur: float, overlay: Path | None, motion: str, out: Path) -> None:
    frames = max(round(dur * FPS), 1)
    zp = _zoompan(motion or "in", frames)
    if overlay:
        graph = f"[0:v]{zp}[v];[v][1:v]overlay=0:0,format=yuv420p[o]"
        inputs = ["-i", str(frame), "-i", str(overlay)]
    else:
        graph = f"[0:v]{zp},format=yuv420p[o]"
        inputs = ["-i", str(frame)]
    _run(["ffmpeg", "-y", *inputs, "-filter_complex", graph, "-map", "[o]",
          "-frames:v", str(frames), "-an", *_ENC, str(out)])


def _render_ai(clip: Path, dur: float, overlay: Path | None, out: Path) -> None:
    base_vf = (f"scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=increase,"
               f"crop={VIDEO_W}:{VIDEO_H},fps={FPS}")
    if overlay:
        _run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(clip), "-i", str(overlay),
              "-t", f"{dur:.3f}", "-filter_complex",
              f"[0:v]{base_vf}[v];[v][1:v]overlay=0:0,format=yuv420p[o]",
              "-map", "[o]", "-an", *_ENC, str(out)])
    else:
        _run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(clip), "-t", f"{dur:.3f}",
              "-vf", f"{base_vf},format=yuv420p", "-an", *_ENC, str(out)])


def _render_cta(bg_color: str, dur: float, overlay: Path | None, out: Path) -> None:
    color = (bg_color or "#EE4D2D").lstrip("#")
    src = f"color=c=0x{color}:s={VIDEO_W}x{VIDEO_H}:d={dur:.3f}:r={FPS}"
    if overlay:
        _run(["ffmpeg", "-y", "-f", "lavfi", "-i", src, "-i", str(overlay),
              "-filter_complex", "[0:v][1:v]overlay=0:0,format=yuv420p[o]",
              "-map", "[o]", "-an", *_ENC, str(out)])
    else:
        _run(["ffmpeg", "-y", "-f", "lavfi", "-i", src, "-an", *_ENC, str(out)])


def _frame_for(scene, tag: str, wd: Path) -> Path:
    """Resolve a kenburns scene's source image and prepare a 9:16 frame."""
    from .frames import prepare_frame
    if scene.image_path:
        src = Path(scene.image_path)
    else:
        digest = hashlib.sha1(scene.image_url.encode()).hexdigest()[:12]
        src = wd / f"src_{digest}.jpg"
        if not src.exists():
            from .video_gen import download_image
            download_image(scene.image_url, src)
    # Leave room for the title header when the scene has one.
    if scene.header:
        return prepare_frame(src, wd / f"frame_{tag}.jpg", focus_y=0.46, max_h_ratio=0.48)
    return prepare_frame(src, wd / f"frame_{tag}.jpg")


def _scaled_durations(plan, voice_dur: float) -> list[float]:
    """AI clips keep their length; the rest of voice + 2s tail is shared by the
    other scenes in proportion to their planned durations (min 3s each)."""
    fixed = sum(s.duration for s in plan.scenes if s.kind == "ai")
    flex_scenes = [s for s in plan.scenes if s.kind != "ai"]
    flex_default = sum(s.duration for s in flex_scenes) or 1.0
    target_total = max(voice_dur + 2.0, fixed + flex_default)
    flex_budget = max(target_total - fixed, len(flex_scenes) * 3.0)
    return [s.duration if s.kind == "ai" else max((s.duration / flex_default) * flex_budget, 3.0)
            for s in plan.scenes]


def compose(plan, clips: dict[int, Path], voice: Path, music: Path | None = None,
            out_name: str = "video.mp4", durations: list[float] | None = None,
            music_volume: float = 0.10, work_dir: Path | None = None) -> Path:
    wd = work_dir or WORK_DIR
    wd.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    durs = durations or _scaled_durations(plan, audio_duration(voice))
    total = sum(durs)

    scene_paths: list[Path] = []
    for i, (scene, dur) in enumerate(zip(plan.scenes, durs)):
        out = wd / f"scene_{i}.mp4"
        tag = str(i)
        overlay = _overlay_png(scene, tag, wd)
        if scene.kind in ("ai", "story") and i in clips:
            _render_ai(clips[i], dur, overlay, out)
        elif scene.kind == "kenburns" and (scene.image_path or scene.image_url):
            motion = scene.motion or MOTIONS[i % len(MOTIONS)]
            _render_kenburns(_frame_for(scene, tag, wd), dur, overlay, motion, out)
        else:
            _render_cta(scene.bg_color, dur, overlay, out)
        scene_paths.append(out)
        print(f"  [compose] scene {i} ({scene.kind}) -> {dur:.1f}s")

    concat_list = wd / "concat.txt"
    concat_list.write_text("".join(f"file '{p.resolve()}'\n" for p in scene_paths))
    silent = wd / "silent.mp4"
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
          "-c", "copy", str(silent)])

    # Voice is padded with silence so the full visual timeline (incl. the CTA)
    # survives, then cut to exactly `total`.
    final = OUTPUT_DIR / out_name
    fade_at = max(total - 1.5, 0)
    if music and music.exists():
        graph = (f"[1:a]apad[vo];[2:a]volume={music_volume},afade=t=out:st={fade_at:.2f}:d=1.5[m];"
                 f"[vo][m]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0[a]")
        inputs = ["-i", str(silent), "-i", str(voice), "-stream_loop", "-1", "-i", str(music)]
    else:
        graph = "[1:a]apad[a]"
        inputs = ["-i", str(silent), "-i", str(voice)]
    _run(["ffmpeg", "-y", *inputs, "-filter_complex", graph, "-map", "0:v", "-map", "[a]",
          "-t", f"{total:.3f}", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
          "-movflags", "+faststart", str(final)])
    print(f"  [compose] final -> {final} ({total:.1f}s)")
    return final


def first_music(subdir: str = "") -> Path | None:
    from .config import MUSIC_DIR
    folder = MUSIC_DIR / subdir if subdir else MUSIC_DIR
    if folder.exists():
        for f in sorted(folder.glob("*.mp3")):
            return f
    return None
