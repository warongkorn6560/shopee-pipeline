"""
Central configuration for both video flows.

  Flow A  Shopee affiliate product videos   (python -m pipeline.run)
  Flow B  Thai storytelling / edutainment   (python -m pipeline.story)

Tunables resolve in this order: real environment (GitHub Actions vars/secrets)
→ local .env → default. Secrets only ever come from the environment or .env.

Cost philosophy: every run estimates its paid-API spend before generating and
aborts if it would exceed COST_CAP_USD. The default providers (local FFmpeg
renderer, ElevenLabs prepaid credits, free-tier LLM, Wikimedia images) cost $0
per video.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
WORK_DIR = ROOT / "work"      # per-run scratch (clips, voice, frames)
OUTPUT_DIR = ROOT / "output"  # final MP4s
ASSETS = ROOT / "assets"
FONT_PATH = ASSETS / "fonts" / "Sarabun-Bold.ttf"
FONT_REGULAR_PATH = ASSETS / "fonts" / "Sarabun-Regular.ttf"
FONT_DISPLAY_PATH = ASSETS / "fonts" / "Kanit-ExtraBold.ttf"
FONT_DISPLAY_MEDIUM_PATH = ASSETS / "fonts" / "Kanit-Bold.ttf"
MUSIC_DIR = ASSETS / "music"

_ENV_KEYS = (
    # secrets
    "FAL_KEY", "ANTHROPIC_API_KEY", "ELEVENLABS_API_KEY", "AI_GATEWAY_API_KEY",
    "OPENAI_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "GOOGLE_SHEET_ID",
    "GOOGLE_SERVICE_ACCOUNT_JSON", "UPLOAD_POST_API_KEY", "UPLOAD_POST_USER",
    "AZURE_TTS_KEY", "AZURE_TTS_REGION", "META_APP_ID", "META_APP_SECRET",
    "INSTAGRAM_ACCESS_TOKEN", "TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET",
    "TIKTOK_REFRESH_TOKEN", "FACEBOOK_PAGE_ID", "FACEBOOK_PAGE_TOKEN",
    # tunables
    "LLM_PROVIDER", "LLM_MODEL", "LLM_BASE_URL", "TTS_PROVIDER", "PUBLISH_MODE",
    "VIDEO_PROVIDER", "COST_CAP_USD", "MONTHLY_BUDGET_USD", "META_GRAPH_VERSION",
    "STORY_NICHE", "STORY_SERIES_NAME", "STORY_IMAGE_PROVIDER", "STORY_IMAGE_MODEL",
    "STORY_AUTO_TOPIC", "STORY_VOICE_ID", "STORY_LLM_MODEL", "STORY_MAX_AI_IMAGES",
    "GITHUB_SERVER_URL", "GITHUB_REPOSITORY", "GITHUB_RUN_ID",
    "DASHBOARD_URL", "PIPELINE_API_KEY",
    "CLAUDE_MODEL", "CLAUDE_EFFORT", "TTS_MODEL", "SHOP_VOICE_ID", "STORY_TARGET_SECONDS", "STORY_MUSIC",
)


def load_env() -> dict[str, str]:
    """Parse .env into a dict and overlay real environment variables."""
    env: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    # Real env vars (GitHub Actions secrets/vars) win over .env
    for k in set(env) | set(_ENV_KEYS):
        if os.environ.get(k):
            env[k] = os.environ[k]
    return env


ENV = load_env()


def _get(name: str, default: str) -> str:
    return ENV.get(name) or default


# ---------------------------------------------------------------------------
# Brand / creative
# ---------------------------------------------------------------------------
SHOPEE_ORANGE = "#EE4D2D"
NICHE = "Pet supplies & toys"
TIKTOK_HANDLE = "@flickfixsummaries"

VIDEO_W = 1080
VIDEO_H = 1920
FPS = 30

# Thai voice. ElevenLabs is the default because the active annual Starter plan
# already includes enough monthly credits for both daily flows.
# eleven_multilingual_v2 does NOT support Thai (it sounded garbled: 65% of words
# survived a speech-to-text check); eleven_v4 + a native Thai voice scored 100%.
TTS_PROVIDER = _get("TTS_PROVIDER", "elevenlabs")  # elevenlabs | azure | fal
TTS_MODEL = _get("TTS_MODEL", "eleven_v4")
THAI_VOICES = {
    "jucSqawHKM1rUNf78oZQ": "Duang — ผู้ชาย เล่าเรื่องเสียงทุ้ม",
    "7XW5JhaNn90bnFojQ5DA": "Mali — ผู้หญิง ชัด เป็นธรรมชาติ",
    "yq05eeRaHPMGuWTVpqeP": "Tonce — ผู้ชาย เป็นกันเอง",
}
SHOP_VOICE_ID = _get("SHOP_VOICE_ID", "7XW5JhaNn90bnFojQ5DA")   # Mali
ELEVENLABS_VOICE_ID = SHOP_VOICE_ID
ELEVENLABS_MODEL = TTS_MODEL
AZURE_VOICE = "th-TH-PremwadeeNeural"

# Creative LLM. With ANTHROPIC_API_KEY set, every script/plan is written by Claude.
CLAUDE_MODEL = _get("CLAUDE_MODEL", "claude-opus-5-5")
CLAUDE_EFFORT = _get("CLAUDE_EFFORT", "high")


# ---------------------------------------------------------------------------
# Flow A video renderer
# ---------------------------------------------------------------------------
# local : product image + Ken Burns motion + captions, rendered by FFmpeg ($0)
# fal   : Flux stills + Kling motion on fal.ai (~$1.40/video, needs fal credits)
VIDEO_PROVIDER = _get("VIDEO_PROVIDER", "local")
LOCAL_SCENES = 5  # hook, problem, reveal, benefit, price — plus the CTA card

FAL_FLUX_MODEL = "fal-ai/flux/dev"
FAL_KLING_MODEL = "fal-ai/kling-video/v2.5-turbo/pro/image-to-video"
FAL_KLING_PRICE_PER_SEC = float(_get("FAL_KLING_PRICE_PER_SEC", "0.07"))
STORY_SCENES = int(_get("STORY_SCENES", "4"))
STORY_CLIP_SECONDS = int(_get("STORY_CLIP_SECONDS", "5"))

# Legacy single-clip i2v path (kept for the fal provider)
FAL_I2V_MODEL = _get("FAL_I2V_MODEL", "fal-ai/veo3/image-to-video")
FAL_I2V_PRICE_PER_SEC = float(_get("FAL_I2V_PRICE_PER_SEC", "0.20"))
AI_CLIPS = int(_get("AI_CLIPS", "1"))
AI_CLIP_SECONDS = int(_get("AI_CLIP_SECONDS", "4"))

# Hard per-video spend ceiling. Orchestrators abort before generating if exceeded.
COST_CAP_USD = float(_get("COST_CAP_USD", "2.00"))
MONTHLY_BUDGET_USD = float(_get("MONTHLY_BUDGET_USD", "30"))


def estimate_video_cost() -> float:
    """Paid-API spend for one Flow A video under the active provider."""
    if VIDEO_PROVIDER == "fal":
        return STORY_SCENES * STORY_CLIP_SECONDS * FAL_KLING_PRICE_PER_SEC
    return 0.0


# ---------------------------------------------------------------------------
# Platform (the dashboard is the queue + review store)
# ---------------------------------------------------------------------------
DASHBOARD_URL = _get("DASHBOARD_URL", "https://pipeline-dashboard-seven-kappa.vercel.app").rstrip("/")


# ---------------------------------------------------------------------------
# Publishing
# ---------------------------------------------------------------------------
# "review"  -> send MP4 to Telegram only; a human posts it (safe default)
# "auto"    -> also publish to the connected social accounts
PUBLISH_MODE = _get("PUBLISH_MODE", "review")
UPLOAD_POST_PLATFORMS = ["tiktok", "instagram", "youtube"]
META_GRAPH_VERSION = _get("META_GRAPH_VERSION", "v23.0")


# ---------------------------------------------------------------------------
# Flow A queue statuses (shared with the dashboard)
# ---------------------------------------------------------------------------
STATUS_READY = "Ready"
STATUS_DONE = "Posted"
STATUS_FAILED = "Failed"


# ---------------------------------------------------------------------------
# Flow B — storytelling / edutainment
# ---------------------------------------------------------------------------
STORY_SERIES_NAME = _get("STORY_SERIES_NAME", "ย้อนรอยการเมืองไทย")
STORY_NICHE = _get(
    "STORY_NICHE",
    "เล่าประวัติศาสตร์การเมืองไทยแบบเป็นกลาง: การเปลี่ยนแปลงการปกครอง รัฐธรรมนูญ การเลือกตั้ง นายกรัฐมนตรี "
    "รัฐสภา พรรคการเมือง และเหตุการณ์สำคัญที่ผ่านมาแล้วอย่างน้อย 15 ปี ด้วยภาพเอกสารจริง ไทม์ไลน์ และแผนที่",
)
STORY_MUSIC = _get("STORY_MUSIC", "politics_bed.mp3")   # file in assets/music/story
# auto      : AI illustration for "scene" visuals when available, real Wikimedia
#             Commons images for maps/photos, designed text cards as last resort
# wikimedia : Wikimedia Commons only (+ cards)
# gateway   : Vercel AI Gateway image model only (+ cards) — needs paid credits
# cards     : designed text cards only (fully offline)
STORY_IMAGE_PROVIDER = _get("STORY_IMAGE_PROVIDER", "auto")
STORY_IMAGE_MODEL = _get("STORY_IMAGE_MODEL", "google/gemini-2.5-flash-image")
STORY_IMAGE_PRICE_USD = 0.039
STORY_MAX_AI_IMAGES = int(_get("STORY_MAX_AI_IMAGES", "4"))
STORY_AUTO_TOPIC = _get("STORY_AUTO_TOPIC", "on").lower() in ("1", "on", "true", "yes")
STORY_VOICE_ID = _get("STORY_VOICE_ID", "jucSqawHKM1rUNf78oZQ")   # Duang
STORY_TARGET_SECONDS = int(_get("STORY_TARGET_SECONDS", "75"))
# Stronger than the Flow A default at factual Thai writing; still allowed on the
# AI Gateway free tier (billed against its free monthly credit, ~$0.005/story).
STORY_LLM_MODEL = _get("STORY_LLM_MODEL", "openai/gpt-4.1-mini")
STORY_ACCENT = "#F2B544"   # map-gold, used for the series badge
STORY_INK = "#0E2A3B"      # deep chart-ink, used for text cards


@dataclass
class Product:
    ref: str            # queue id in the dashboard (or csv-<row> offline)
    name: str
    price_thb: str
    commission_pct: str
    sales: str
    affiliate_url: str
    niche: str
    notes: str
    image_url: str

    @property
    def has_image(self) -> bool:
        return self.image_url.startswith("http")


@dataclass
class Scene:
    """One segment of the video timeline."""
    kind: str               # "story" | "ai" | "kenburns" | "cta"
    duration: float
    caption: str = ""
    i2v_prompt: str = ""    # motion prompt for Kling animation
    flux_prompt: str = ""   # image-generation prompt for Flux (kind=="story")
    image_url: str = ""     # source image for ai/kenburns
    image_path: str = ""    # local source image (takes precedence over image_url)
    bg_color: str = ""      # for cta
    motion: str = ""        # kenburns motion: in | out | pan-left | pan-right | up | down
    header: str = ""        # small title shown at the top of the frame
    badge: str = ""         # series badge above the header
    credit: str = ""        # image attribution shown at the bottom
    big: bool = False       # large centered caption (hook / title scenes)


@dataclass
class VideoPlan:
    """Full creative plan returned by a scriptwriter."""
    script: str                       # full Thai voiceover
    caption: str
    hashtags: list[str]
    hook_alt_1: str = ""
    hook_alt_2: str = ""
    scenes: list[Scene] = field(default_factory=list)
