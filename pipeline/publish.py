"""
Publish the finished video.

Two paths:
  review (default) : upload the MP4 to your Telegram + a ready-to-paste caption,
                     hashtags, affiliate link and backup hooks. You tap to post.
                     Free, and keeps a human quality gate while you tune.
  auto             : ALSO push to socials via upload-post.com (TikTok/IG/YouTube).
                     Free tier = 10 uploads/month; paid above that.

Shopee video upload has NO API — that step is always manual (≈30s in the app).
The Telegram message includes the affiliate link so that's one tap too.
"""

from __future__ import annotations

from pathlib import Path

import requests

from .config import ENV, PUBLISH_MODE, UPLOAD_POST_PLATFORMS


def _telegram(method: str) -> str:
    return f"https://api.telegram.org/bot{ENV['TELEGRAM_BOT_TOKEN']}/{method}"


def caption_block(plan, product) -> str:
    tags = " ".join(plan.hashtags)
    return (
        f"✅ NEW VIDEO READY\n\n"
        f"📦 {product.name}\n"
        f"💰 {product.price_thb} THB | commission {product.commission_pct}%\n\n"
        f"📝 Caption:\n{plan.caption}\n\n"
        f"#️⃣ {tags}\n\n"
        f"🔗 Affiliate link (update IG + TikTok bio to this):\n{product.affiliate_url}\n\n"
        f"🔁 Backup hooks:\n1) {plan.hook_alt_1}\n2) {plan.hook_alt_2}\n\n"
        f"👉 Steps: 1) Update IG & TikTok bio link → 2) Video auto-posted ✓ → 3) Upload to Shopee Video app."
    )


def send_to_telegram(video: Path, plan, product) -> bool:
    cap = caption_block(plan, product)
    # Telegram captions cap at 1024 chars; send video then a full text follow-up.
    with video.open("rb") as f:
        r = requests.post(
            _telegram("sendVideo"),
            data={"chat_id": ENV["TELEGRAM_CHAT_ID"], "caption": cap[:1000]},
            files={"video": (video.name, f, "video/mp4")},
            timeout=300,
        )
    ok = r.ok and r.json().get("ok", False)
    if not ok:
        # fallback: at least send the text + a note (video may exceed 50MB)
        requests.post(_telegram("sendMessage"),
                      data={"chat_id": ENV["TELEGRAM_CHAT_ID"],
                            "text": cap + f"\n\n(⚠️ video send failed: {r.text[:200]})"})
    elif len(cap) > 1000:
        # only send a follow-up if caption was truncated on the video
        requests.post(_telegram("sendMessage"),
                      data={"chat_id": ENV["TELEGRAM_CHAT_ID"], "text": cap})
    return ok


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


def publish(video: Path, plan, product, mode: str | None = None) -> dict:
    mode = mode or PUBLISH_MODE
    result = {"telegram": send_to_telegram(video, plan, product)}
    if mode == "auto":
        result["upload_post"] = auto_post(video, plan, product)
        caption = plan.caption + " " + " ".join(plan.hashtags) + "\n\n🔗 ดูลิงก์ในโปรไฟล์ได้เลย 👆"
        from . import tiktok as _tiktok
        result["tiktok"] = _tiktok.publish(video, caption)
        from . import instagram as _ig
        result["instagram"] = _ig.publish(video, caption)
    return result
