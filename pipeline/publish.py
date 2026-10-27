"""
Publish finished videos.

  review (default) : send the MP4 + a ready-to-paste caption to Telegram.
                     A human posts it. Free, and keeps a quality gate.
  auto             : ALSO publish to the connected social accounts.

Shopee Video upload has NO API — that step is always manual (≈30s in the app).
"""

from __future__ import annotations

import json
from pathlib import Path

import requests

from .config import ENV, PUBLISH_MODE, UPLOAD_POST_PLATFORMS

_TG_CAPTION_LIMIT = 1000


def _telegram(method: str) -> str:
    return f"https://api.telegram.org/bot{ENV['TELEGRAM_BOT_TOKEN']}/{method}"


def review_buttons(video_id: str) -> str:
    """Inline approve/reject buttons; the dashboard's Telegram webhook handles the callbacks."""
    return json.dumps({"inline_keyboard": [[
        {"text": "✅ อนุมัติและโพสต์", "callback_data": f"ap:{video_id}"},
        {"text": "❌ ไม่ผ่าน", "callback_data": f"rj:{video_id}"},
    ]]})


def telegram_send_video(video: Path, text: str, reply_markup: str = "") -> bool:
    """Send a video with caption; long text follows as a separate message."""
    chat = ENV["TELEGRAM_CHAT_ID"]
    with video.open("rb") as f:
        r = requests.post(
            _telegram("sendVideo"),
            data={"chat_id": chat, "caption": text[:_TG_CAPTION_LIMIT], "supports_streaming": "true",
                  **({"reply_markup": reply_markup} if reply_markup else {})},
            files={"video": (video.name, f, "video/mp4")},
            timeout=300,
        )
    ok = r.ok and r.json().get("ok", False)
    if not ok:
        requests.post(_telegram("sendMessage"), timeout=60,
                      data={"chat_id": chat, "text": text + f"\n\n(⚠️ video send failed: {r.text[:200]})"})
    elif len(text) > _TG_CAPTION_LIMIT:
        requests.post(_telegram("sendMessage"), timeout=60, data={"chat_id": chat, "text": text})
    return ok


# ---------------------------------------------------------------------------
# Flow A — Shopee affiliate
# ---------------------------------------------------------------------------
def social_caption(plan) -> str:
    """The text to paste when posting (also shown with a copy button in the dashboard)."""
    return f"{plan.caption}\nกดลิงก์ในโปรไฟล์เลย 👆\n{' '.join(plan.hashtags)}".strip()


def caption_block(plan, product, review_url: str = "") -> str:
    text = (
        f"✅ NEW VIDEO READY\n\n"
        f"{social_caption(plan)}\n\n"
        f"📦 {product.name[:80]}\n"
        f"🔗 {product.affiliate_url}"
    )
    return text + (f"\n\n▶️ ตรวจในเว็บ: {review_url}" if review_url else "")


def send_to_telegram(video: Path, plan, product, review_url: str = "") -> bool:
    return telegram_send_video(video, caption_block(plan, product, review_url))


def auto_post(video: Path, plan, product) -> dict:
    """Push to socials via upload-post.com. Returns the API response."""
    key = ENV.get("UPLOAD_POST_API_KEY")
    if not key:
        return {"skipped": "UPLOAD_POST_API_KEY not set"}
    title = (plan.caption + " " + " ".join(plan.hashtags))[:150]
    data = [("user", ENV.get("UPLOAD_POST_USER", "default"))]
    for p in UPLOAD_POST_PLATFORMS:
        data.append(("platform[]", p))
    data.append(("title", title))
    with video.open("rb") as f:
        r = requests.post(
            "https://api.upload-post.com/api/upload",
            headers={"Authorization": f"Apikey {key}"},
            data=data,
            files={"video": (video.name, f, "video/mp4")},
            timeout=600,
        )
    try:
        return r.json()
    except Exception:
        return {"status_code": r.status_code, "text": r.text[:300]}


def _safe(fn, *args) -> dict:
    try:
        return fn(*args)
    except Exception as exc:  # noqa: BLE001 — one platform failing must not abort the run
        return {"error": f"{type(exc).__name__}: {str(exc)[:300]}"}


def publish(video: Path, plan, product, mode: str | None = None, review_url: str = "") -> dict:
    mode = mode or PUBLISH_MODE
    result = {"telegram": send_to_telegram(video, plan, product, review_url)}
    if mode == "auto":
        result["upload_post"] = _safe(auto_post, video, plan, product)
        caption = plan.caption + " " + " ".join(plan.hashtags) + "\n\n🔗 ดูลิงก์ในโปรไฟล์ได้เลย 👆"
        from . import instagram as _ig
        from . import tiktok as _tiktok
        result["tiktok"] = _safe(_tiktok.publish, video, caption)
        result["instagram"] = _safe(_ig.publish, video, caption)
    return result


# ---------------------------------------------------------------------------
# Flow B — storytelling
# ---------------------------------------------------------------------------
def publish_story(video: Path, review_text: str, social_caption: str,
                  mode: str | None = None, video_url: str = "", video_id: str = "", title: str = "",
                  instagram: dict | None = None) -> dict:
    """`instagram`: the channel's own Instagram account ({userId, token}) when it has one."""
    mode = mode or PUBLISH_MODE
    buttons = review_buttons(video_id) if video_id and mode != "auto" else ""
    result: dict = {"telegram": telegram_send_video(video, review_text, buttons)}
    if mode == "auto":
        from . import facebook as _fb
        from . import instagram as _ig
        from . import tiktok as _tiktok
        from .config import STORY_CHANNEL_ID, STORY_CHANNEL_PRIMARY
        if STORY_CHANNEL_ID:
            # Each dashboard channel is one Facebook Page with its own token.
            def _page():
                from . import hub
                try:
                    ch = hub.channel_token(STORY_CHANNEL_ID)
                except hub.PlatformError:
                    ch = {}
                if not (ch.get("pageId") and ch.get("token")):
                    return {"skipped": "channel has no Facebook page"}      # e.g. an Instagram-only channel
                return _fb.publish_reel(video, social_caption, ch["pageId"], ch["token"])
            result["facebook"] = _safe(_page)
        else:
            result["facebook"] = _safe(_fb.publish_reel, video, social_caption)
        if instagram and instagram.get("token"):     # the channel's own Instagram account
            result["instagram"] = _safe(_ig.publish, video, social_caption[:2000], video_url, instagram)
        if STORY_CHANNEL_PRIMARY:  # the single TikTok/Instagram account follows the primary page
            result["tiktok"] = _safe(_tiktok.publish, video, social_caption[:2000])
            if "instagram" not in result:
                result["instagram"] = _safe(_ig.publish, video, social_caption[:2000], video_url)
            from . import youtube as _yt
            result["youtube"] = _safe(_yt.publish, video, title or social_caption.split("\n")[0], social_caption)
    return result
