"""
YouTube Shorts upload (YouTube Data API v3, resumable upload).

The dashboard's YouTube connect stores YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET /
YOUTUBE_REFRESH_TOKEN as GitHub secrets. Until the Google project passes the
YouTube API Services audit, YouTube forces API uploads to private.
"""

from __future__ import annotations

import json
from pathlib import Path

import requests

from .config import ENV

TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"


def _access_token() -> str:
    r = requests.post(TOKEN_URL, timeout=30, data={
        "client_id": ENV["YOUTUBE_CLIENT_ID"], "client_secret": ENV["YOUTUBE_CLIENT_SECRET"],
        "refresh_token": ENV["YOUTUBE_REFRESH_TOKEN"], "grant_type": "refresh_token"})
    data = r.json()
    if "access_token" not in data:
        # no response echo: it could carry tokens, and Actions logs of this repo are public
        raise RuntimeError(f"YouTube token refresh failed: {data.get('error') or r.status_code}")
    return data["access_token"]


def _title(title: str) -> str:
    title = " ".join(title.split())[:100]
    return f"{title} #Shorts" if len(title) + 8 <= 100 else title


def publish(video: Path, title: str, caption: str) -> dict:
    if not all(ENV.get(k) for k in ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN")):
        return {"skipped": "YouTube not connected — connect it in dashboard Settings"}
    token = _access_token()
    meta = {
        "snippet": {"title": _title(title), "description": caption[:4900], "categoryId": "15",
                    "defaultLanguage": "th", "defaultAudioLanguage": "th"},
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
    }
    size = video.stat().st_size
    start = requests.post(f"{UPLOAD_URL}?uploadType=resumable&part=snippet,status", timeout=60,
                          headers={"Authorization": f"Bearer {token}",
                                   "Content-Type": "application/json; charset=UTF-8",
                                   "X-Upload-Content-Type": "video/mp4",
                                   "X-Upload-Content-Length": str(size)},
                          data=json.dumps(meta))
    if start.status_code == 403 and "quotaExceeded" in start.text:
        return {"skipped": "quota"}  # ~1600 units per upload, 10,000 per day
    if not start.ok:
        raise RuntimeError(f"YouTube upload init failed: {start.status_code} {start.text[:300]}")
    with video.open("rb") as f:
        up = requests.put(start.headers["Location"], data=f, timeout=900,
                          headers={"Authorization": f"Bearer {token}", "Content-Type": "video/mp4"})
    if up.status_code == 403 and "quotaExceeded" in up.text:
        return {"skipped": "quota"}
    if not up.ok:
        raise RuntimeError(f"YouTube upload failed: {up.status_code} {up.text[:300]}")
    body = up.json()
    out = {"video_id": body["id"], "status": "published"}
    if body.get("status", {}).get("privacyStatus") != "public":
        out["note"] = "private_until_audit"
    return out
