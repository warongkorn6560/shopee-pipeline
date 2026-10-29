"""
Take posted story clips down everywhere the API allows, and mark them so no backfill re-posts them.

  python -m pipeline.story.takedown <videoId> [<videoId> ...]

Facebook (page token) and YouTube are deleted; Instagram is deleted when the API allows it.
Each platform entry keeps its id with status "deleted", so the backfills treat it as done.
TikTok has no delete API (our uploads sit as inbox drafts anyway).
"""

from __future__ import annotations

import sys

import requests

from .. import hub
from ..config import ENV
from ..facebook import GRAPH
from ..instagram import IG_GRAPH
from ..youtube import _access_token


def _fb(video_id: str, token: str) -> str:
    r = requests.delete(f"{GRAPH}/{video_id}", params={"access_token": token}, timeout=30)
    return "deleted" if r.ok else f"failed {r.status_code}: {r.json().get('error', {}).get('message', '')[:120]}"


def _ig(media_id: str, token: str) -> str:
    r = requests.delete(f"{IG_GRAPH}/{media_id}", params={"access_token": token}, timeout=30)
    return "deleted" if r.ok else f"failed {r.status_code}: {r.json().get('error', {}).get('message', '')[:120]}"


def _yt(video_id: str) -> str:
    r = requests.delete("https://www.googleapis.com/youtube/v3/videos", params={"id": video_id},
                        headers={"Authorization": f"Bearer {_access_token()}"}, timeout=30)
    return "deleted" if r.status_code == 204 else f"failed {r.status_code}: {r.text[:160]}"


def takedown(video_id: str) -> dict:
    v = hub._call("video", {"id": video_id})
    pub = dict(v.get("published") or {})
    print(f"▶ {video_id}: {v.get('title', '')}")
    fb = pub.get("facebook") or {}
    if isinstance(fb, dict) and fb.get("video_id") and v.get("token"):
        fb["status"] = _fb(fb["video_id"], v["token"])
    ig = pub.get("instagram") or {}
    own = v.get("instagram") if isinstance(v.get("instagram"), dict) else {}
    ig_token = own.get("token") or ENV.get("INSTAGRAM_ACCESS_TOKEN")
    if isinstance(ig, dict) and ig.get("media_id") and ig_token:
        ig["status"] = _ig(ig["media_id"], ig_token)
    yt = pub.get("youtube") or {}
    if isinstance(yt, dict) and yt.get("video_id") and yt.get("video_id") != "none":
        yt["status"] = _yt(yt["video_id"])
    # never re-post this clip: give every platform a done-looking entry
    pub["facebook"] = fb or {"video_id": "none", "status": "deleted"}
    pub["instagram"] = ig if ig.get("media_id") else {"media_id": "none", "status": "deleted"}
    pub["youtube"] = yt if yt.get("video_id") else {"video_id": "none", "status": "deleted"}
    pub["takedown"] = True
    print(f"  facebook {pub['facebook'].get('status')} · instagram {pub['instagram'].get('status')} · "
          f"youtube {pub['youtube'].get('status')}")
    hub._call("video-posted", {"id": video_id, "published": pub, "posted": False})
    return pub


if __name__ == "__main__":
    for vid in sys.argv[1:]:
        try:
            takedown(vid)
        except Exception as e:  # noqa: BLE001 — keep going through the list
            print(f"  {vid}: {type(e).__name__}: {str(e)[:200]}")
