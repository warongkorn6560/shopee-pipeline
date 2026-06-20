"""
TikTok Content Posting API v2 — direct video upload to @flickfixsummaries.

Auth flow (one-time setup):
  1. Run:  python -m pipeline.tiktok auth
  2. Open the printed URL in your browser, log in as @flickfixsummaries
  3. You'll be redirected to https://localhost/?code=XXX&...
  4. Copy the full URL and paste it back
  5. Tokens are printed — add TIKTOK_REFRESH_TOKEN to GitHub secrets

Every pipeline run then uses the refresh token to get a fresh access token.
"""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs

import requests

from .config import ENV

TIKTOK_AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TIKTOK_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
TIKTOK_INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"
TIKTOK_STATUS_URL = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"
REDIRECT_URI = "https://github.com/warongkorn6560/shopee-pipeline"


def _client():
    return ENV["TIKTOK_CLIENT_KEY"], ENV["TIKTOK_CLIENT_SECRET"]


def auth_url() -> str:
    client_key, _ = _client()
    params = {
        "client_key": client_key,
        "scope": "video.publish,user.info.basic",
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "state": "shopee_pipeline",
    }
    return f"{TIKTOK_AUTH_URL}?{urlencode(params)}"


def exchange_code(code: str) -> dict:
    client_key, client_secret = _client()
    r = requests.post(TIKTOK_TOKEN_URL, data={
        "client_key": client_key,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
    }, timeout=30)
    return r.json()


def refresh_token(refresh_tok: str) -> str:
    """Exchange refresh token for a fresh access token. Returns access_token."""
    client_key, client_secret = _client()
    r = requests.post(TIKTOK_TOKEN_URL, data={
        "client_key": client_key,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_tok,
    }, timeout=30)
    data = r.json()
    if "data" not in data or "access_token" not in data.get("data", {}):
        raise RuntimeError(f"TikTok token refresh failed: {data}")
    return data["data"]["access_token"]


def post_video(video: Path, title: str, access_token: str) -> str:
    """Upload video to TikTok. Returns publish_id."""
    size = video.stat().st_size
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
    }

    # 1) init upload
    r = requests.post(TIKTOK_INIT_URL, headers=headers, json={
        "post_info": {
            "title": title[:2200],
            "privacy_level": "PUBLIC_TO_EVERYONE",
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
            "video_cover_timestamp_ms": 1000,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": size,
            "chunk_size": size,
            "total_chunk_count": 1,
        },
    }, timeout=30)
    resp = r.json()
    if "data" not in resp:
        raise RuntimeError(f"TikTok init failed: {resp}")

    upload_url = resp["data"]["upload_url"]
    publish_id = resp["data"]["publish_id"]

    # 2) upload the file in one chunk
    with video.open("rb") as f:
        video_bytes = f.read()

    r = requests.put(
        upload_url,
        headers={
            "Content-Range": f"bytes 0-{size - 1}/{size}",
            "Content-Length": str(size),
            "Content-Type": "video/mp4",
        },
        data=video_bytes,
        timeout=300,
    )
    if r.status_code not in (200, 201, 206):
        raise RuntimeError(f"TikTok upload failed: {r.status_code} {r.text[:300]}")

    return publish_id


def publish(video: Path, title: str) -> dict:
    """Full flow: refresh token → upload video → return result."""
    refresh_tok = ENV.get("TIKTOK_REFRESH_TOKEN", "")
    if not refresh_tok:
        return {"skipped": "TIKTOK_REFRESH_TOKEN not set — run: python -m pipeline.tiktok auth"}

    access_token = refresh_token(refresh_tok)
    publish_id = post_video(video, title, access_token)
    return {"publish_id": publish_id, "status": "uploaded"}


# ---------------------------------------------------------------------------
# CLI: python -m pipeline.tiktok auth
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "auth":
        print("\n1. Open this URL in your browser and log in as @flickfixsummaries:\n")
        print(auth_url())
        print("\n2. After approving, you'll be redirected to https://localhost/?code=...")
        print("   Copy the FULL URL from your browser and paste it here:\n")
        redirect = input("Paste URL: ").strip()
        parsed = parse_qs(urlparse(redirect).query)
        code = parsed.get("code", [None])[0]
        if not code:
            print("❌ No code found in URL")
            sys.exit(1)
        result = exchange_code(code)
        print("\n✅ Tokens received:")
        print(f"   access_token:  {result.get('data', {}).get('access_token', 'N/A')}")
        print(f"   refresh_token: {result.get('data', {}).get('refresh_token', 'N/A')}")
        print("\n→ Add TIKTOK_REFRESH_TOKEN to GitHub secrets:")
        print(f"   gh secret set TIKTOK_REFRESH_TOKEN --body \"{result.get('data', {}).get('refresh_token', '')}\"")
