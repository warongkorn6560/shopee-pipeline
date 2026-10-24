"""
Client for the dashboard's pipeline API — the system's own queue and review store.

Both flows claim their next item here, report status back, and upload the
finished MP4 for review in the dashboard. Auth: Bearer PIPELINE_API_KEY.
"""

from __future__ import annotations

import time
from pathlib import Path

import requests

from .config import DASHBOARD_URL, ENV


class PlatformError(RuntimeError):
    pass


class BudgetStop(RuntimeError):
    """Month-to-date Claude spend reached CLAUDE_MONTHLY_BUDGET: make nothing this run."""


def configured() -> bool:
    return bool(ENV.get("PIPELINE_API_KEY"))


def _call(action: str, payload: dict, timeout: int = 60) -> dict:
    key = ENV.get("PIPELINE_API_KEY")
    if not key:
        raise PlatformError("PIPELINE_API_KEY is not set")
    last: Exception | None = None
    for attempt in range(3):
        try:
            r = requests.post(f"{DASHBOARD_URL}/api/pipeline/{action}", json=payload, timeout=timeout,
                              headers={"Authorization": f"Bearer {key}"})
            if r.status_code >= 500:
                raise PlatformError(f"{action}: HTTP {r.status_code} {r.text[:200]}")
            if not r.ok:
                raise PlatformError(f"{action}: HTTP {r.status_code} {r.text[:300]}")
            return r.json()
        except (requests.RequestException, PlatformError) as e:
            last = e
            if isinstance(e, PlatformError) and "HTTP 4" in str(e):
                break  # client errors won't fix themselves
            time.sleep(3 * (attempt + 1))
    raise PlatformError(str(last))


def claim(flow: str, channel_id: str = "") -> dict:
    """Next Ready item for the flow (now marked Producing), or {"item": None, ...}.
    With a channel id, only that channel's stories (and its previous topics) count."""
    res = _call("claim", {"flow": flow, **({"channelId": channel_id} if channel_id else {})})
    if res.get("stop") == "budget":
        raise BudgetStop(res.get("message") or "Claude monthly budget reached")
    return res


def budget() -> dict | None:
    """{spent, budget, stop, notify} from the dashboard; None when it can't tell (no cap enforced here)."""
    try:
        return _call("budget", {})
    except PlatformError as e:
        print(f"  [budget] unavailable: {str(e)[:120]}")
        return None


def stop_for_budget(flow_label: str) -> bool:
    """True when the monthly Claude budget is used up; tells Telegram once a day."""
    b = budget()
    if not b or not b.get("stop"):
        return False
    msg = (f"⏸ {flow_label}: หยุดทำคลิปชั่วคราว ค่า Claude เดือนนี้ ${float(b.get('spent', 0)):.2f} "
           f"ถึงงบ ${float(b.get('budget', 0)):.0f} แล้ว — ปรับงบได้ใน dashboard → ตั้งค่า → AI & เสียง")
    print("  " + msg)
    if b.get("notify") and ENV.get("TELEGRAM_BOT_TOKEN") and ENV.get("TELEGRAM_CHAT_ID"):
        try:
            requests.post(f"https://api.telegram.org/bot{ENV['TELEGRAM_BOT_TOKEN']}/sendMessage", timeout=30,
                          data={"chat_id": ENV["TELEGRAM_CHAT_ID"], "text": msg})
        except requests.RequestException:
            pass
    return True


def update(flow: str, item_id: str, **patch) -> None:
    _call("update", {"flow": flow, "id": item_id, "patch": patch})


def create_story(topic: str, angle: str, status: str = "Producing", source: str = "manual",
                 channel_id: str = "") -> dict:
    """Start (or queue) a topic; an existing entry with the same topic is reused."""
    return _call("stories", {"topic": topic, "angle": angle, "status": status, "source": source,
                             **({"channelId": channel_id} if channel_id else {})})["item"]


def channel_token(channel_id: str) -> dict:
    """{channelId, pageId, name, token} for a connected Facebook Page channel."""
    return _call("channel-token", {"channelId": channel_id})


def upload_video(flow: str, mp4: Path) -> dict:
    """Upload to the private store; returns {videoId, pathname, reviewUrl}."""
    meta = _call("upload-url", {"flow": flow})
    last = ""
    for attempt in range(3):
        try:
            with mp4.open("rb") as f:
                r = requests.put(meta["uploadUrl"], data=f, timeout=600, headers={"content-type": "video/mp4"})
            if r.ok:
                return {"videoId": meta["videoId"], "pathname": meta["pathname"], "reviewUrl": meta["reviewUrl"]}
            last = f"HTTP {r.status_code} {r.text[:200]}"
        except requests.RequestException as e:
            last = str(e)
        time.sleep(5 * (attempt + 1))
    raise PlatformError(f"video upload failed: {last}")


def register_video(**video) -> dict:
    return _call("videos", video)
