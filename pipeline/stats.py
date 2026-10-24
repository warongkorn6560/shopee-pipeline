"""
Collect view/engagement numbers for posted story videos and store them in the
dashboard (stats.yml, every 6 hours). The numbers also steer auto-topics: the
writer is shown what performed best and worst.

  python -m pipeline.stats
"""

from __future__ import annotations

import datetime as dt
import sys

import requests

from . import hub
from .config import ENV
from .facebook import GRAPH
from .instagram import IG_GRAPH


def _num(v) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------------------
# Platforms
# ---------------------------------------------------------------------------
def _facebook(video_id: str, token: str) -> dict | None:
    out = {}
    r = requests.get(f"{GRAPH}/{video_id}/video_insights", timeout=30,
                     params={"metric": "blue_reels_play_count,post_video_social_actions", "access_token": token})
    if not r.ok:
        print(f"    [fb] insights {r.status_code}: {r.json().get('error', {}).get('message', '')[:160]}")
    for m in (r.json().get("data") or []) if r.ok else []:
        val = (m.get("values") or [{}])[0].get("value")
        if m.get("name") == "blue_reels_play_count":
            out["plays"] = _num(val)
        elif m.get("name") == "post_video_social_actions" and isinstance(val, dict):
            out["shares"] = _num(val.get("SHARE"))
    r = requests.get(f"{GRAPH}/{video_id}", timeout=30, params={
        "fields": "likes.summary(true).limit(0),comments.summary(true).limit(0)", "access_token": token})
    if r.ok:
        d = r.json()
        out["likes"] = _num(d.get("likes", {}).get("summary", {}).get("total_count"))
        out["comments"] = _num(d.get("comments", {}).get("summary", {}).get("total_count"))
    return out or None


def _instagram(media_id: str, token: str) -> dict | None:
    for metrics in ("views,reach,likes,comments,shares,saved", "plays,reach,likes,comments,shares,saved"):
        r = requests.get(f"{IG_GRAPH}/{media_id}/insights", timeout=30,
                         params={"metric": metrics, "access_token": token})
        if not r.ok:
            print(f"    [ig] insights {r.status_code}: {r.json().get('error', {}).get('message', '')[:160]}")
        if r.ok:
            out = {m["name"]: _num((m.get("values") or [{}])[0].get("value")) for m in r.json().get("data", [])}
            if "plays" in out:
                out["views"] = out.pop("plays")
            return out
    return None


def _youtube_token() -> str | None:
    if not all(ENV.get(k) for k in ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN")):
        return None
    from .youtube import _access_token
    return _access_token()


def _youtube(ids: list[str], token: str) -> dict[str, dict]:
    out = {}
    for k in range(0, len(ids), 50):
        r = requests.get("https://www.googleapis.com/youtube/v3/videos", timeout=30,
                         headers={"Authorization": f"Bearer {token}"},
                         params={"part": "statistics", "id": ",".join(ids[k:k + 50])})
        for item in (r.json().get("items") or []) if r.ok else []:
            s = item.get("statistics", {})
            out[item["id"]] = {"views": _num(s.get("viewCount")), "likes": _num(s.get("likeCount")),
                               "comments": _num(s.get("commentCount"))}
    return out


def _ok_id(published: dict, platform: str, key: str) -> str | None:
    entry = (published or {}).get(platform)
    return entry.get(key) if isinstance(entry, dict) and not entry.get("error") else None


def _totals(stats: dict) -> dict:
    views = sum(_num(s.get("plays") or s.get("views")) for p, s in stats.items() if isinstance(s, dict))
    acts = sum(_num(s.get(k)) for s in stats.values() if isinstance(s, dict)
               for k in ("likes", "comments", "shares", "saved"))
    return {"totalViews": views, "engagement": round(acts / views, 4) if views else 0.0}


# ---------------------------------------------------------------------------
def collect() -> int:
    videos = hub._call("videos-list", {"flow": "story", "days": 60}).get("videos", [])
    print(f"▶ stats for {len(videos)} posted videos")
    page_tokens: dict[str, str] = {}

    def page_token(channel_id: str | None) -> str | None:
        key = channel_id or ""
        if key not in page_tokens:
            try:
                page_tokens[key] = hub.channel_token(channel_id)["token"] if channel_id else ENV.get("FACEBOOK_PAGE_TOKEN", "")
            except hub.PlatformError:
                page_tokens[key] = ENV.get("FACEBOOK_PAGE_TOKEN", "")
        return page_tokens[key] or None

    yt_token = None
    try:
        yt_token = _youtube_token()
    except Exception as e:  # noqa: BLE001
        print(f"  [yt] token failed: {e}")
    yt_ids = [i for v in videos if (i := _ok_id(v.get("published"), "youtube", "video_id"))]
    yt = _youtube(yt_ids, yt_token) if yt_token and yt_ids else {}
    ig_token = ENV.get("INSTAGRAM_ACCESS_TOKEN", "")

    updated = 0
    for v in videos:
        pub, stats = v.get("published") or {}, {}
        try:
            if (fid := _ok_id(pub, "facebook", "video_id")) and (tok := page_token(v.get("channelId"))):
                if s := _facebook(fid, tok):
                    stats["facebook"] = s
            if (mid := _ok_id(pub, "instagram", "media_id")) and ig_token:
                if s := _instagram(mid, ig_token):
                    stats["instagram"] = s
            if (yid := _ok_id(pub, "youtube", "video_id")) and yid in yt:
                stats["youtube"] = yt[yid]
        except requests.RequestException as e:
            print(f"  {v['id']}: {type(e).__name__}")
        if not stats:
            continue
        stats.update(_totals(stats), updatedAt=dt.datetime.now(dt.timezone.utc).isoformat())
        hub._call("video-stats", {"id": v["id"], "stats": stats})
        updated += 1
        print(f"  {v.get('title', '')[:40]}: {stats['totalViews']} views · eng {stats['engagement']:.1%} · "
              + " ".join(f"{p}={s}" for p, s in stats.items() if isinstance(s, dict)))
    print(f"  ✓ updated {updated}")
    return 0


def performance(limit: int = 5) -> tuple[list[str], list[str]]:
    """(best, worst) clip descriptions for the topic writer; empty when unknown."""
    try:
        videos = hub._call("videos-list", {"flow": "story", "days": 60}).get("videos", [])
    except Exception:  # noqa: BLE001 — feedback is optional
        return [], []
    rated = [v for v in videos if (v.get("stats") or {}).get("totalViews")]
    if len(rated) < 6:
        return [], []
    rated.sort(key=lambda v: v["stats"]["totalViews"], reverse=True)
    fmt = lambda v: f"{v.get('topic') or v.get('title')} — {v['stats']['totalViews']} views, engagement {v['stats'].get('engagement', 0):.1%}"
    return [fmt(v) for v in rated[:limit]], [fmt(v) for v in rated[-limit:]]


if __name__ == "__main__":
    sys.exit(collect())
