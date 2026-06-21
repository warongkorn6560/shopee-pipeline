"""
Instagram Graph API (new Instagram Login) — post Reels to @flickfixsummaries.

One-time setup:
  1. Meta app "ShopeePipeline-IG" (app ID 2126951697871097) is already created.
  2. In Instagram app settings → Apps and Websites → Tester Invites → Accept
     (the developer portal sent an invite to @flickfixsummaries)
  3. gh secret set META_APP_ID     --body "2126951697871097"
     gh secret set META_APP_SECRET --body "..."   # from Meta developer portal → Show
  4. python -m pipeline.instagram auth   # opens browser for Instagram OAuth
     gh secret set INSTAGRAM_ACCESS_TOKEN --body "IGAAx..."

Token lasts 60 days. Re-run step 4 before expiry.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs

import requests

from .config import ENV

IG_AUTH = "https://api.instagram.com/oauth"
IG_GRAPH = "https://graph.instagram.com/v22.0"
REDIRECT_URI = "https://warongkorn6560.github.io/shopee-pipeline/"
SCOPES = "instagram_business_basic,instagram_business_content_publish"


def _app() -> tuple[str, str]:
    return ENV["META_APP_ID"], ENV["META_APP_SECRET"]


def auth_url() -> str:
    app_id, _ = _app()
    return (
        f"{IG_AUTH}/authorize?"
        + urlencode({
            "client_id": app_id,
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPES,
            "response_type": "code",
            "state": "shopee_ig",
        })
    )


def exchange_code(code: str) -> str:
    """Exchange auth code → long-lived token (60 days)."""
    app_id, app_secret = _app()

    # Short-lived token (1 hour)
    r = requests.post(f"{IG_AUTH}/access_token", data={
        "client_id": app_id,
        "client_secret": app_secret,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
        "code": code,
    }, timeout=30)
    data = r.json()
    if "access_token" not in data:
        raise RuntimeError(f"Instagram short-lived token exchange failed: {data}")
    short_token = data["access_token"]

    # Exchange for long-lived token (60 days)
    r = requests.get(f"{IG_GRAPH}/access_token", params={
        "grant_type": "ig_exchange_token",
        "client_secret": app_secret,
        "access_token": short_token,
    }, timeout=30)
    data = r.json()
    if "access_token" not in data:
        raise RuntimeError(f"Instagram long-lived token exchange failed: {data}")
    return data["access_token"]


def _ig_user_id(token: str) -> str:
    """Return the Instagram user ID for the authenticated account."""
    r = requests.get(f"{IG_GRAPH}/me", params={
        "fields": "id,username",
        "access_token": token,
    }, timeout=30)
    data = r.json()
    if "id" not in data:
        raise RuntimeError(f"Failed to get Instagram user ID: {data}")
    return data["id"]


def _host_video(video: Path) -> str:
    """Upload video to litterbox.catbox.moe (72h) and return a public HTTPS URL."""
    with video.open("rb") as f:
        r = requests.post(
            "https://litterbox.catbox.moe/resources/internals/api.php",
            data={"reqtype": "fileupload", "time": "72h"},
            files={"fileToUpload": (video.name, f, "video/mp4")},
            timeout=120,
        )
    if r.status_code != 200 or not r.text.startswith("https://"):
        raise RuntimeError(f"Video upload to litterbox failed: {r.status_code} {r.text[:200]}")
    return r.text.strip()


def post_reel(video: Path, caption: str, token: str) -> str:
    """Upload a Reel and publish it. Returns the published Instagram media ID."""
    ig_user_id = _ig_user_id(token)
    video_url = _host_video(video)

    # Step 1 — create upload container
    r = requests.post(f"{IG_GRAPH}/{ig_user_id}/media", params={
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "access_token": token,
    }, timeout=60)
    resp = r.json()
    if "id" not in resp:
        raise RuntimeError(f"Instagram container creation failed: {resp}")
    creation_id = resp["id"]

    # Step 2 — wait for Instagram to finish processing (typically 30-90 s)
    for _ in range(24):
        time.sleep(10)
        r = requests.get(f"{IG_GRAPH}/{creation_id}", params={
            "fields": "status_code,status",
            "access_token": token,
        }, timeout=30)
        data = r.json()
        status = data.get("status_code", "")
        if status == "FINISHED":
            break
        if status == "ERROR":
            raise RuntimeError(f"Instagram container processing failed: {data}")
    else:
        raise RuntimeError("Instagram container timed out after 4 minutes")

    # Step 3 — publish
    r = requests.post(f"{IG_GRAPH}/{ig_user_id}/media_publish", params={
        "creation_id": creation_id,
        "access_token": token,
    }, timeout=30)
    resp = r.json()
    if "id" not in resp:
        raise RuntimeError(f"Instagram publish failed: {resp}")
    return resp["id"]


def publish(video: Path, caption: str) -> dict:
    """Publish a Reel. Returns result dict (never raises — errors are returned)."""
    token = ENV.get("INSTAGRAM_ACCESS_TOKEN", "")
    if not token:
        return {"skipped": "INSTAGRAM_ACCESS_TOKEN not set — run: python -m pipeline.instagram auth"}
    try:
        media_id = post_reel(video, caption, token)
        return {"media_id": media_id, "status": "published"}
    except Exception as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# CLI: python -m pipeline.instagram auth
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] != "auth":
        print("Usage: python -m pipeline.instagram auth")
        sys.exit(1)

    print("""
Instagram setup checklist:
  ✓ ShopeePipeline-IG app created at developers.facebook.com (app ID: 2126951697871097)
  ✓ instagram_business_content_publish permission added
  ✓ META_APP_ID and META_APP_SECRET are set (env or .env file)
  ✓ @flickfixsummaries is a Professional (Creator/Business) account
  ✓ In Instagram: Settings → Apps and Websites → Tester Invites → Accept

Open this URL in a browser where you are logged in as @flickfixsummaries:
""")
    print(auth_url())
    print("""
After authorizing, you will be redirected. Copy the full URL from your browser
and paste it here:
""")
    redirect = input("URL: ").strip()
    parsed = parse_qs(urlparse(redirect).query)
    code = parsed.get("code", [None])[0]
    if not code:
        print("❌  No 'code' parameter found in the URL")
        sys.exit(1)

    token = exchange_code(code)
    print(f"\n✅  Long-lived access token (valid ~60 days):\n{token}")
    print("\nAdd it to GitHub secrets:")
    print(f'  gh secret set INSTAGRAM_ACCESS_TOKEN --body "{token}"')
    print("\nAlso set the app credentials if not done yet:")
    print('  gh secret set META_APP_ID --body "2126951697871097"')
    print('  gh secret set META_APP_SECRET --body "<from developers.facebook.com → Show>"')
    print("\nRe-run this command before day 55 to refresh.")
