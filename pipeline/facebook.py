"""
Facebook Page Reels publishing (Graph API, resumable upload).

One-time setup:
  1. In the Meta app (developers.facebook.com → your app) add the
     "Facebook Login for Business" product and put
     https://warongkorn6560.github.io/shopee-pipeline/ in Valid OAuth Redirect URIs.
  2. python -m pipeline.facebook auth
     → approve in the browser, paste the redirect URL back, pick your Page.
     The Page ID and a non-expiring Page token are saved to GitHub Secrets
     (FACEBOOK_PAGE_ID / FACEBOOK_PAGE_TOKEN) via the gh CLI.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests

from .config import ENV, META_GRAPH_VERSION

GRAPH = f"https://graph.facebook.com/{META_GRAPH_VERSION}"
REDIRECT_URI = "https://warongkorn6560.github.io/shopee-pipeline/"
SCOPES = "pages_show_list,pages_read_engagement,pages_manage_posts"


def publish_reel(video: Path, description: str, page_id: str = "", token: str = "") -> dict:
    page_id = page_id or ENV.get("FACEBOOK_PAGE_ID", "")
    token = token or ENV.get("FACEBOOK_PAGE_TOKEN", "")
    if not (page_id and token):
        return {"skipped": "FACEBOOK_PAGE_ID / FACEBOOK_PAGE_TOKEN not set — run: python -m pipeline.facebook auth"}

    start = requests.post(f"{GRAPH}/{page_id}/video_reels", timeout=60,
                          data={"upload_phase": "start", "access_token": token})
    start.raise_for_status()
    video_id = start.json()["video_id"]
    upload_url = start.json().get("upload_url") or f"https://rupload.facebook.com/video-upload/{META_GRAPH_VERSION}/{video_id}"

    size = video.stat().st_size
    with video.open("rb") as f:
        up = requests.post(upload_url, data=f, timeout=600, headers={
            "Authorization": f"OAuth {token}", "offset": "0", "file_size": str(size)})
    up.raise_for_status()

    finish = requests.post(f"{GRAPH}/{page_id}/video_reels", timeout=120, data={
        "upload_phase": "finish", "video_id": video_id, "video_state": "PUBLISHED",
        "description": description[:2200], "access_token": token})
    finish.raise_for_status()
    return {"video_id": video_id, "status": "published" if finish.json().get("success") else "processing"}


# ---------------------------------------------------------------------------
# OAuth helper
# ---------------------------------------------------------------------------
def auth_url() -> str:
    return f"https://www.facebook.com/{META_GRAPH_VERSION}/dialog/oauth?" + urlencode({
        "client_id": ENV["META_APP_ID"], "redirect_uri": REDIRECT_URI,
        "scope": SCOPES, "response_type": "code", "state": "shopee_fb"})


def _pages_for_code(code: str) -> list[dict]:
    app_id, secret = ENV["META_APP_ID"], ENV["META_APP_SECRET"]
    short = requests.get(f"{GRAPH}/oauth/access_token", timeout=30, params={
        "client_id": app_id, "client_secret": secret, "redirect_uri": REDIRECT_URI, "code": code})
    short.raise_for_status()
    long = requests.get(f"{GRAPH}/oauth/access_token", timeout=30, params={
        "grant_type": "fb_exchange_token", "client_id": app_id, "client_secret": secret,
        "fb_exchange_token": short.json()["access_token"]})
    long.raise_for_status()
    pages = requests.get(f"{GRAPH}/me/accounts", timeout=30, params={
        "access_token": long.json()["access_token"], "fields": "id,name,access_token"})
    pages.raise_for_status()
    return pages.json().get("data", [])


def _gh_secret(name: str, value: str) -> bool:
    try:
        subprocess.run(["gh", "secret", "set", name], input=value, text=True,
                       check=True, capture_output=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] != "auth":
        print("Usage: python -m pipeline.facebook auth")
        sys.exit(1)
    print("\nOpen this URL while logged in to the Facebook account that manages your Page:\n")
    print(auth_url())
    redirect = input("\nAfter approving, paste the full URL you were redirected to:\nURL: ").strip()
    code = parse_qs(urlparse(redirect).query).get("code", [None])[0]
    if not code:
        sys.exit("No 'code' parameter found in that URL.")
    pages = _pages_for_code(code)
    if not pages:
        sys.exit("No Pages returned. Make sure you granted access to at least one Page.")
    for i, p in enumerate(pages, 1):
        print(f"  {i}. {p['name']} ({p['id']})")
    choice = int(input("Pick a Page number: ").strip() or "1") - 1
    page = pages[choice]
    if _gh_secret("FACEBOOK_PAGE_ID", page["id"]) and _gh_secret("FACEBOOK_PAGE_TOKEN", page["access_token"]):
        print(f"\n✅ Saved FACEBOOK_PAGE_ID and FACEBOOK_PAGE_TOKEN for “{page['name']}” to GitHub Secrets.")
    else:
        print("\n⚠️ Could not run `gh secret set`. Set these two secrets manually in GitHub:")
        print(f"  FACEBOOK_PAGE_ID = {page['id']}")
        print("  FACEBOOK_PAGE_TOKEN = (the access_token for this page from /me/accounts)")
