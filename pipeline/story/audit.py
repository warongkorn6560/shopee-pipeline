"""
Audit posted story clips for bad pictures (drawings, dead or stuffed animals, wrong species).

  python -m pipeline.story.audit <channel_id> [days]

For every clip: sample frames, tile them into a numbered contact sheet, ask the vision model
which cells are bad, and write output/audit/report.json plus the sheets for a human look.
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import requests
from PIL import Image, ImageDraw

from .. import hub
from ..config import OUTPUT_DIR
from ..llm import look

OUT = OUTPUT_DIR / "audit"
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["bad_cells", "notes"],
          "properties": {"bad_cells": {"type": "array", "items": {"type": "integer"}},
                         "notes": {"type": "string"}}}


def _frames(mp4: Path, every: float = 2.5) -> list[Image.Image]:
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(mp4), "-vf", f"fps=1/{every},scale=270:-1",
                        f"{d}/f%03d.jpg"], check=True)
        return [Image.open(p).convert("RGB") for p in sorted(Path(d).glob("f*.jpg"))]


def _sheet(frames: list[Image.Image], cols: int = 6) -> Image.Image:
    w, h = frames[0].size
    rows = (len(frames) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w, rows * h), (0, 0, 0))
    d = ImageDraw.Draw(sheet)
    for i, f in enumerate(frames):
        x, y = (i % cols) * w, (i // cols) * h
        sheet.paste(f, (x, y))
        d.rectangle((x, y, x + 46, y + 40), fill=(255, 255, 0))
        d.text((x + 8, y + 8), str(i + 1), fill=(0, 0, 0), font_size=28)
    return sheet


def check_clip(mp4: Path, title: str, sheet_path: Path | None = None) -> dict:
    """{bad_cells, notes} for one rendered clip; bad_cells empty = every picture looks right.
    None from the vision model (no Claude, or a failed call) comes back as checked=False."""
    sheet = _sheet(_frames(mp4))
    if sheet_path:
        sheet.save(sheet_path, quality=80)
    buf = io.BytesIO()
    s = sheet.copy()
    s.thumbnail((1568, 1568))
    s.save(buf, "JPEG", quality=85)
    verdict = look(buf.getvalue(),
                   f"These numbered cells are frames from a Thai wildlife short about: {title!r}. "
                   "Satellite maps, title cards, year cards and graphics are fine. List the cell numbers "
                   "whose main picture is BAD: a drawing, painting or old illustration plate instead of a "
                   "photo; a dead, roadkill, hunted, stuffed or museum-specimen animal, skull or bones; or "
                   "an animal that is clearly not the one the title is about. 'notes' = at most 25 words.",
                   SCHEMA)
    return {**verdict, "checked": True} if verdict else {"bad_cells": [], "notes": "vision check failed",
                                                          "checked": False}


def audit(channel_id: str, days: int = 3) -> list[dict]:
    OUT.mkdir(parents=True, exist_ok=True)
    vids = [v for v in hub._call("videos-list", {"flow": "story", "days": days})["videos"]
            if v.get("channelId") == channel_id]
    report = []
    for v in vids:
        full = hub._call("video", {"id": v["id"]})
        mp4 = OUT / f"{v['id']}.mp4"
        mp4.write_bytes(requests.get(full["url"], timeout=300).content)
        verdict = check_clip(mp4, v["title"], OUT / f"{v['id']}.jpg")
        mp4.unlink()
        row = {"id": v["id"], "title": v["title"], "created": v["createdAt"], **verdict,
               "published": {k: (x.get("video_id") or x.get("media_id")) if isinstance(x, dict) else x
                             for k, x in (v.get("published") or {}).items()}}
        print(json.dumps(row, ensure_ascii=False))
        report.append(row)
    (OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))
    return report


if __name__ == "__main__":
    audit(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 3)
