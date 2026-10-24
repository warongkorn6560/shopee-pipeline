"""
Post one already-rendered video from the dashboard's review page.

The dashboard dispatches post-video.yml when a reviewer approves a video.
This downloads the MP4 from the private store and publishes it to the
video's channel (Facebook Page) plus TikTok/Instagram when that channel is
the primary one, then reports the result back.

  python -m pipeline.post_video <videoId>
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import requests

from . import facebook, hub, instagram, tiktok
from .publish import _safe
from .run import posted_somewhere


def main(video_id: str) -> int:
    v = hub._call("video", {"id": video_id})
    print(f"▶ Posting {video_id}: {v.get('title', '')} → {v.get('channelName') or 'primary page'}")
    caption = v.get("caption", "")
    with tempfile.TemporaryDirectory() as tmp:
        mp4 = Path(tmp) / "video.mp4"
        r = requests.get(v["url"], timeout=600)
        r.raise_for_status()
        mp4.write_bytes(r.content)
        res: dict = {}
        if v.get("pageId") and v.get("token"):
            res["facebook"] = _safe(facebook.publish_reel, mp4, caption, v["pageId"], v["token"])
        else:
            res["facebook"] = _safe(facebook.publish_reel, mp4, caption)
        if v.get("primary", True):
            res["tiktok"] = _safe(tiktok.publish, mp4, caption[:2000])
            res["instagram"] = _safe(instagram.publish, mp4, caption[:2000])
    print(f"  publish: {res}")
    hub._call("video-posted", {"id": video_id, "published": res, "posted": posted_somewhere(res)})
    return 0 if posted_somewhere(res) else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python -m pipeline.post_video <videoId>")
    sys.exit(main(sys.argv[1]))
