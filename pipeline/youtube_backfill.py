"""
Post already-published story videos to platforms they never reached — made before the platform
was connected, skipped by YouTube's daily quota, or refused by Instagram's "too many actions"
throttle during a burst. Most-viewed first, a few per run so the platforms see a steady pace.

  python -m pipeline.youtube_backfill [max] [platform]     # platform: youtube (default) | instagram
"""

from __future__ import annotations

import sys

from . import hub
from .post_video import main as post

ID_KEY = {"youtube": "video_id", "instagram": "media_id"}


def _has(v: dict, platform: str) -> bool:
    entry = (v.get("published") or {}).get(platform)
    return isinstance(entry, dict) and bool(entry.get(ID_KEY[platform]))


def run(limit: int = 3, platform: str = "youtube") -> int:
    videos = hub._call("videos-list", {"flow": "story", "days": 30}).get("videos", [])
    todo = [v for v in videos if not _has(v, platform)]
    todo.sort(key=lambda v: -((v.get("stats") or {}).get("totalViews") or 0))
    print(f"▶ {len(todo)} posted videos without {platform}; posting up to {limit}")
    for v in todo[:limit]:
        try:
            post(v["id"], platform)
        except Exception as e:  # noqa: BLE001 — one failure must not stop the rest
            print(f"  {v['id']}: {type(e).__name__}: {str(e)[:200]}")
    return 0


if __name__ == "__main__":
    sys.exit(run(int(sys.argv[1]) if len(sys.argv) > 1 else 3, sys.argv[2] if len(sys.argv) > 2 else "youtube"))
