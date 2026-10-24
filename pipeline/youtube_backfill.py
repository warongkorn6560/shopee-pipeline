"""
Upload already-posted story videos that never reached YouTube (e.g. made before YouTube was
connected, or skipped when the daily quota ran out), most-viewed first.

  python -m pipeline.youtube_backfill [max]
"""

from __future__ import annotations

import sys

from . import hub
from .post_video import main as post


def _has_youtube(v: dict) -> bool:
    yt = (v.get("published") or {}).get("youtube")
    return isinstance(yt, dict) and bool(yt.get("video_id"))


def run(limit: int = 3) -> int:
    videos = hub._call("videos-list", {"flow": "story", "days": 30}).get("videos", [])
    todo = [v for v in videos if not _has_youtube(v)]
    todo.sort(key=lambda v: -((v.get("stats") or {}).get("totalViews") or 0))
    print(f"▶ {len(todo)} posted videos without YouTube; uploading up to {limit}")
    for v in todo[:limit]:
        try:
            post(v["id"], "youtube")
        except Exception as e:  # noqa: BLE001 — one failure must not stop the rest
            print(f"  {v['id']}: {type(e).__name__}: {str(e)[:200]}")
    return 0


if __name__ == "__main__":
    sys.exit(run(int(sys.argv[1]) if len(sys.argv) > 1 else 3))
