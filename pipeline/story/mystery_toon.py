"""
"toon3d" style: the fair-play mystery script (same writer, hook rule and recurring detective as mystery3d)
acted out by a small stylized 3D world that the pipeline renders itself — no paid image or video API.

The world lives in story/toon3d/ (three.js scene + a headless-Chromium renderer on software WebGL, so it
runs on a CPU-only GitHub runner). This module turns a MysteryPlan and the narration timing into a render
job (set, suspects' looks, one camera shot per beat) and returns one mp4 per beat for mystery3d_render,
which adds the subtitles, evidence tags, countdown and sound.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

from ..config import ENV, FPS
from .mystery import MysteryPlan
from .mystery3d import FORMAT_NOTES, write_mystery3d

TOON_DIR = Path(__file__).parent / "toon3d"
SETS = ("office", "apartment", "cafe")
SET_FOR = {"office": "office", "school": "office", "apartment": "apartment", "mansion": "apartment",
           "forest": "apartment", "cafe": "cafe", "train": "cafe", "street": "cafe"}
TOON_NOTES = FORMAT_NOTES + """
- setting must be "office", "apartment" or "cafe" (the series has these three sets).
- Clue objects should be one of: key, clock, footprint, cup, phone, letter, umbrella, ring, photo, door,
  light, car — pick clue_icon to match exactly what the narration shows."""

SKINS = (0xF0C8A0, 0xE9B98F, 0xD9A47A, 0xC68B62, 0xB07650)
HAIRS = (0x15110F, 0x2B1D16, 0x4A3226, 0x6B6B70, 0x1F1A2E)
TOPS = (0xB03A2E, 0x2E6FB0, 0x3A8F5A, 0x7B4FA8, 0xD9862B, 0x2F8F8F, 0xC94F7C, 0x5C6B2E)
BOTTOMS = (0x2B2B33, 0x3B3A4A, 0x4A3A2A, 0x23324A)
ROLE_ACCESSORY = (
    (("แม่บ้าน", "แม่ครัว", "แม่ค้า", "พนักงานร้าน", "บาริสต้า"), "apron"),
    (("คนขับ", "ช่าง", "ยาม", "รปภ", "ไรเดอร์", "คนส่ง"), "cap"),
    (("เชฟ", "พ่อครัว"), "chef"),
    (("ผู้จัดการ", "หัวหน้า", "เลขา", "บัญชี", "พนักงาน", "ทนาย", "เจ้าของ", "ประธาน"), "tie"),
    (("นักเรียน", "นักศึกษา", "ลูกชาย", "ลูกสาว", "หลาน", "เด็กฝึกงาน"), "bag"),
    (("ป้า", "ยาย", "คุณนาย", "แม่", "เพื่อนบ้าน"), "earrings"),
)
FEMININE = ("ป้า", "ยาย", "นาง", "แม่", "คุณนาย", "สาว", "พี่สาว", "น้องสาว", "ลูกสาว", "เลขา", "แม่บ้าน", "หญิง")


def _h(text: str) -> int:
    return int(hashlib.sha1(text.encode()).hexdigest()[:8], 16)


def suspect_looks(suspects: list[dict]) -> list[dict]:
    """A stable, distinct look per suspect from their name and role (no image model needed)."""
    looks, used_tops = [], set()
    for k, s in enumerate(suspects):
        name, role = s.get("name", ""), s.get("role", "")
        h = _h(name + role)
        acc = next((a for words, a in ROLE_ACCESSORY if any(w in role or w in name for w in words)),
                   ("scarf", "glasses", "none", "bag")[h % 4])
        fem = any(w in role or w in name for w in FEMININE)
        style = ("bun", "long")[h % 2] if fem else ("short", "spiky", "bald", "short")[h % 4]
        top = next(c for c in TOPS[h % len(TOPS):] + TOPS if c not in used_tops)
        used_tops.add(top)
        look = {"skin": SKINS[(h >> 4) % len(SKINS)], "hair": HAIRS[(h >> 8) % len(HAIRS)], "hairStyle": style,
                "top": top, "bottom": BOTTOMS[(h >> 12) % len(BOTTOMS)], "height": 0.93 + ((h >> 16) % 13) / 100,
                "build": 0.9 + ((h >> 20) % 30) / 100, "accent": TOPS[(h >> 24) % len(TOPS)]}
        if acc == "glasses":
            look["glasses"] = 0x222222
        elif acc != "none":
            look["accessory"] = acc
        looks.append(look)
    return looks


def write_toon(topic: str, angle: str = "") -> MysteryPlan:
    plan = write_mystery3d(topic, (angle + "\n\n" + TOON_NOTES).strip())
    plan.style = "toon3d"
    return plan


def shots(plan: MysteryPlan) -> list[str]:
    """One camera shot per beat: hook, arrive (first scene), think (later scenes), suspects, clue, pause,
    reveal / reveal2, ending."""
    out, arrived, reveals = [], False, 0
    for i, s in enumerate(plan.scenes):
        v = s.visual
        if i == 0:
            out.append("hook")
        elif v == "scene":
            out.append("think" if arrived else "arrive")
            arrived = True
        elif v == "reveal":
            out.append("reveal" if reveals == 0 else "reveal2")
            reveals += 1
        else:
            out.append(v)
        if v == "suspects":
            arrived = True
    return out


def render_beats(plan: MysteryPlan, beat_durs: list[float], run_dir: Path) -> dict[int, Path]:
    """Render every beat except the pause to run_dir/toon_<i>.mp4. Returns {beat: mp4}."""
    if not (TOON_DIR / "node_modules" / "puppeteer").exists():
        raise RuntimeError(f"toon3d renderer not installed: run `npm ci && npx puppeteer browsers install "
                           f"chrome-headless-shell` in {TOON_DIR}")
    width = int(ENV.get("TOON3D_WIDTH") or os.environ.get("TOON3D_WIDTH") or 1080)
    first_clue = next((s.icon for s in plan.scenes if s.visual == "clue"), "ring")
    beats, clips = [], {}
    for i, (sc, shot, d) in enumerate(zip(plan.scenes, shots(plan), beat_durs)):
        out = run_dir / f"toon_{i}.mp4"
        icon = sc.icon if shot == "clue" else first_clue if shot == "hook" else ""
        beats.append({"shot": shot, "frames": max(int(round(d * FPS)), 1), "icon": icon, "focus": sc.focus,
                      "emotion": sc.emotion, "out": "" if shot == "pause" else str(out)})
        if shot != "pause":
            clips[i] = out
    job = {"width": width, "height": width * 16 // 9, "fps": FPS, "set": SET_FOR.get(plan.setting, "apartment"),
           "answer": plan.answer_suspect, "suspects": suspect_looks(plan.suspects), "beats": beats}
    job_path = run_dir / "toon_job.json"
    job_path.write_text(json.dumps(job, ensure_ascii=False, indent=1))
    t0 = time.time()
    print(f"  [toon3d] rendering {sum(b['frames'] for b in beats if b['out'])} frames at {width}px "
          f"({job['set']}, {len(job['suspects'])} suspects)…")
    subprocess.run(["node", str(TOON_DIR / "render.mjs"), str(job_path)], check=True)
    print(f"  [toon3d] 3D shots done in {time.time() - t0:.0f}s")
    return clips
