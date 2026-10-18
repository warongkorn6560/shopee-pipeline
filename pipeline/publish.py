"""
Publish finished videos.

  review (default) : send the MP4 + a ready-to-paste caption to Telegram.
                     A human posts it. Free, and keeps a quality gate.
  auto             : ALSO publish to the connected social accounts.

Shopee Video upload has NO API — that step is always manual (≈30s in the app).
"""

from __future__ import annotations

from pathlib import Path

import requests

from .config import ENV, PUBLISH_MODE, UPLOAD_POST_PLATFORMS

_TG_CAPTION_LIMIT = 1000


def _telegram(method: str) -> str:
    return f"https://api.telegram.org/bot{ENV['TELEGRAM_BOT_TOKEN']}/{method}"


def telegram_send_video(video: Path, text: str) -> bool:
    """Send a video with caption; long text follows as a separate message."""
    chat = ENV["TELEGRAM_CHAT_ID"]
    with video.open("rb") as f:
        r = requests.post(
            _telegram("sendVideo"),
            data={"chat_id": chat, "caption": text[:_TG_CAPTION_LIMIT], "supports_streaming": "true"},
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
def caption_block(plan, product) -> str:
    tags = " ".join(plan.hashtags)
    return (
        f"✅ NEW VIDEO READY\n\n"
        f"{plan.caption}\n"
        f"กดลิงค์ในโปรไฟล์เลย 👆\n"
        f"{tags}\n\n"
        f"📦 {product.name[:80]}\n"
        f"🔗 {product.affiliate_url}"
    )


def send_to_telegram(video: Path, plan, product) -> bool:
    return telegram_send_video(video, caption_block(plan, product))


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


def publish(video: Path, plan, product, mode: str | None = None) -> dict:
    mode = mode or PUBLISH_MODE
    result = {"telegram": send_to_telegram(video, plan, product)}
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
                  mode: str | None = None) -> dict:
    mode = mode or PUBLISH_MODE
    result: dict = {"telegram": telegram_send_video(video, review_text)}
    if mode == "auto":
        from . import facebook as _fb
        from . import instagram as _ig
        from . import tiktok as _tiktok
        result["facebook"] = _safe(_fb.publish_reel, video, social_caption)
        result["tiktok"] = _safe(_tiktok.publish, video, social_caption[:2000])
        result["instagram"] = _safe(_ig.publish, video, social_caption[:2000])
    return result
