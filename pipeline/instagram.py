"""
Instagram Graph API — post Reels to @flickfixsummaries.

One-time setup:
  1. Create a Meta app at https://developers.facebook.com
       - Add product "Instagram Graph API"
       - Add Redirect URI: https://warongkorn6560.github.io/shopee-pipeline/
       - Request permission: instagram_content_publish (needed for app review later)
  2. gh secret set META_APP_ID     --body "..."
     gh secret set META_APP_SECRET --body "..."
  3. Make @flickfixsummaries a Creator/Business account linked to a Facebook Page
       Instagram → Settings → Account type → Switch to Professional
  4. python -m pipeline.instagram auth   # generates the access token
     gh secret set INSTAGRAM_ACCESS_TOKEN --body "EAA..."

Token lasts 60 days. Re-run step 4 before expiry.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs

import requests

from .config import ENV

META_API = "https://graph.facebook.com/v19.0"
REDIRECT_URI = "https://warongkorn6560.github.io/shopee-pipeline/"
SCOPES = "instagram_basic,instagram_content_publish,pages_read_engagement,pages_show_list"


def _app() -> tuple[str, str]:
    return ENV["META_APP_ID"], ENV["META_APP_SECRET"]


def auth_url() -> str:
    app_id, _ = _app()
    return (
        "https://www.facebook.com/v19.0/dialog/oauth?"
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

    r = requests.get(f"{META_API}/oauth/access_token", params={
        "client_id": app_id,
        "client_secret": app_secret,
        "redirect_uri": REDIRECT_URI,
        "code": code,
    }, timeout=30)
    data = r.json()
    if "access_token" not in data:
        raise RuntimeError(f"Meta short-lived token exchange failed: {data}")

    r = requests.get(f"{META_API}/oauth/access_token", params={
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "fb_exchange_token": data["access_token"],
    }, timeout=30)
    data = r.json()
    if "access_token" not in data:
        raise RuntimeError(f"Meta long-lived token exchange failed: {data}")
    return data["access_token"]


def _ig_account(token: str) -> tuple[str, str]:
    """Return (ig_user_id, page_access_token) for the first linked Instagram account."""
    r = requests.get(f"{META_API}/me/accounts", params={"access_token": token}, timeout=30)
    pages = r.json().get("data", [])
    if not pages:
        raise RuntimeError(
            "No Facebook Pages found. The authorized account must manage a Page "
            "linked to @flickfixsummaries."
        )

    page_id = pages[0]["id"]
    page_token = pages[0]["access_token"]

    r = requests.get(f"{META_API}/{page_id}", params={
        "fields": "instagram_business_account",
        "access_token": page_token,
    }, timeout=30)
    ig = r.json().get("instagram_business_account")
    if not ig:
        raise RuntimeError(
            f"No Instagram Business/Creator account is linked to Facebook Page "
            f"'{pages[0]['name']}'. "
            "In Instagram → Settings → Account type → Switch to Professional, "
            "then link to your Facebook Page."
        )
    return ig["id"], page_token


def _host_video(video: Path) -> str:
    """Upload video to 0x0.st and return a public HTTPS URL."""
    with video.open("rb") as f:
        r = requests.post("https://0x0.st", files={"file": f}, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"Video upload to 0x0.st failed: {r.status_code} {r.text[:200]}")
    return r.text.strip()


def post_reel(video: Path, caption: str, token: str) -> str:
    """Upload a Reel and publish it. Returns the published Instagram media ID."""
    ig_user_id, page_token = _ig_account(token)
    video_url = _host_video(video)

    # Step 1 — create upload container
    r = requests.post(f"{META_API}/{ig_user_id}/media", params={
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "access_token": page_token,
    }, timeout=60)
    resp = r.json()
    if "id" not in resp:
        raise RuntimeError(f"Instagram container creation failed: {resp}")
    creation_id = resp["id"]

    # Step 2 — wait for Instagram to finish processing (typically 30-90 s)
    for _ in range(24):
        time.sleep(10)
        r = requests.get(f"{META_API}/{creation_id}", params={
            "fields": "status_code,status",
            "access_token": page_token,
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
    r = requests.post(f"{META_API}/{ig_user_id}/media_publish", params={
        "creation_id": creation_id,
        "access_token": page_token,
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
  ✓ @flickfixsummaries is a Creator or Business account
  ✓ It is linked to a Facebook Page
  ✓ META_APP_ID and META_APP_SECRET are set (env or .env file)
  ✓ Redirect URI https://warongkorn6560.github.io/shopee-pipeline/ is added to the Meta app

Open this URL in a browser where you are logged in as the Facebook account
that manages @flickfixsummaries:
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
    print("\nRe-run this command before day 55 to refresh.")
