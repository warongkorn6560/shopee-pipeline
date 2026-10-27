"""
Post already-published story videos to platforms they never reached — made before the platform
was connected, skipped by YouTube's daily quota, or refused by Instagram's "too many actions"
throttle during a burst. Most-viewed first, spaced `gap` minutes apart so the platforms see a
steady pace; stops early once the platform says its limit is reached.

  python -m pipeline.youtube_backfill [max] [platform] [gap]   # platform: youtube (default) | instagram
"""

from __future__ import annotations

import sys
import time

from . import hub
from .post_video import publish_video

ID_KEY = {"youtube": "video_id", "instagram": "media_id"}
# the platform refuses more today — waiting for the next run is the only option
LIMIT_HIT = ("exceeded the number of videos", "quotaExceeded", "too many actions", "rate limit")


def _has(v: dict, platform: str) -> bool:
    entry = (v.get("published") or {}).get(platform)
    return isinstance(entry, dict) and bool(entry.get(ID_KEY[platform]))


def run(limit: int = 3, platform: str = "youtube", gap: float = 0) -> int:
    videos = hub._call("videos-list", {"flow": "story", "days": 30}).get("videos", [])
    todo = [v for v in videos if not _has(v, platform)]
    todo.sort(key=lambda v: -((v.get("stats") or {}).get("totalViews") or 0))
    print(f"▶ {len(todo)} posted videos without {platform}; posting up to {limit}")
    for k, v in enumerate(todo[:limit]):
        if k and gap:
            time.sleep(gap * 60)
        try:
            entry = publish_video(v["id"], platform).get(platform) or {}
        except Exception as e:  # noqa: BLE001 — one failure must not stop the rest
            print(f"  {v['id']}: {type(e).__name__}: {str(e)[:200]}")
            continue
        if any(m.lower() in str(entry.get("error", "")).lower() for m in LIMIT_HIT):
            print(f"  ⏸ {platform} limit reached — the next run continues")
            break
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    sys.exit(run(int(a[0]) if a else 3, a[1] if len(a) > 1 else "youtube", float(a[2]) if len(a) > 2 else 0))
