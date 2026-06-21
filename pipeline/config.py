"""
Central configuration for the Shopee affiliate AI-video pipeline.

Everything tunable lives here: which AI model, video length, cost caps, voice,
brand colors. Secrets come from .env (never hard-code them).

Cost philosophy: the orchestrator estimates the fal.ai spend BEFORE generating
and aborts if a single video would exceed COST_CAP_USD. This keeps you safely
under the monthly budget no matter what.
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
MUSIC_DIR = ASSETS / "music"


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
    # Real env vars (e.g. from GitHub Actions secrets) win over .env
    for k in list(env) + [
        "FAL_KEY", "ANTHROPIC_API_KEY", "ELEVENLABS_API_KEY",
        "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "GOOGLE_SHEET_ID",
        "GOOGLE_SERVICE_ACCOUNT_JSON", "UPLOAD_POST_API_KEY",
        "AZURE_TTS_KEY", "AZURE_TTS_REGION",
        "AI_GATEWAY_API_KEY", "LLM_PROVIDER", "LLM_MODEL", "OPENAI_API_KEY",
        "META_APP_ID", "META_APP_SECRET", "INSTAGRAM_ACCESS_TOKEN",
    ]:
        if os.environ.get(k):
            env[k] = os.environ[k]
    return env


ENV = load_env()


# ---------------------------------------------------------------------------
# Brand / creative
# ---------------------------------------------------------------------------
SHOPEE_ORANGE = "#EE4D2D"
NICHE = "Pet supplies & toys"
TIKTOK_HANDLE = "@flickfixsummaries"

VIDEO_W = 1080
VIDEO_H = 1920
FPS = 30

# Thai voice. ElevenLabs multilingual_v2 supports Thai; Azure has a native voice.
TTS_PROVIDER = os.environ.get("TTS_PROVIDER", "azure")  # azure | elevenlabs | fal
ELEVENLABS_VOICE_ID = "XrExE9yKIg1WjnnlVkGX"  # "Matilda" – warm female, multilingual
ELEVENLABS_MODEL = "eleven_multilingual_v2"
AZURE_VOICE = "th-TH-PremwadeeNeural"


# ---------------------------------------------------------------------------
# AI video generation (fal.ai)
# ---------------------------------------------------------------------------
# Models on fal.ai (verified May 2026). Pick per goal:
#   veo3/image-to-video                       $0.20/s  BEST at "human using product" (default)
#   kling-video/v2.5-turbo/pro/image-to-video $0.07/s  cheap, photoreal, but won't add a human
#   wan/v2.5/image-to-video                   $0.05/s  cheapest
# Default = Veo 4s hero clip: reliably composes a real person using the product.
# Story-scene pipeline: Flux text-to-image → Kling image-to-video
# 4 story scenes × 5s × $0.07 = $1.40/video
FAL_FLUX_MODEL = "fal-ai/flux/dev"
FAL_KLING_MODEL = "fal-ai/kling-video/v2.5-turbo/pro/image-to-video"
FAL_KLING_PRICE_PER_SEC = float(os.environ.get("FAL_KLING_PRICE_PER_SEC", "0.07"))
STORY_SCENES = int(os.environ.get("STORY_SCENES", "4"))
STORY_CLIP_SECONDS = int(os.environ.get("STORY_CLIP_SECONDS", "5"))

# Legacy i2v (kept for backwards compat / override)
FAL_I2V_MODEL = os.environ.get("FAL_I2V_MODEL", "fal-ai/veo3/image-to-video")
FAL_I2V_PRICE_PER_SEC = float(os.environ.get("FAL_I2V_PRICE_PER_SEC", "0.20"))
AI_CLIPS = int(os.environ.get("AI_CLIPS", "1"))
AI_CLIP_SECONDS = int(os.environ.get("AI_CLIP_SECONDS", "4"))

# Hard per-video spend ceiling. Orchestrator aborts before generating if exceeded.
COST_CAP_USD = float(os.environ.get("COST_CAP_USD", "2.00"))

# Monthly budget tracking (informational; written to output/spend_log.json)
MONTHLY_BUDGET_USD = float(os.environ.get("MONTHLY_BUDGET_USD", "30"))


def estimate_video_cost() -> float:
    """Estimate fal.ai spend for one video: 4 story scenes × 5s × $0.07."""
    return STORY_SCENES * STORY_CLIP_SECONDS * FAL_KLING_PRICE_PER_SEC


# ---------------------------------------------------------------------------
# Publishing
# ---------------------------------------------------------------------------
# "review"  -> send MP4 to Telegram, you tap to post (safe default while tuning)
# "auto"    -> also push to upload-post.com for direct posting to socials
PUBLISH_MODE = os.environ.get("PUBLISH_MODE", "review")
UPLOAD_POST_PLATFORMS = ["tiktok", "instagram", "youtube"]


# ---------------------------------------------------------------------------
# Source sheet layout (Inbox tab) — column letters
# ---------------------------------------------------------------------------
# A Date | B Name | C Price | D Commission% | E Sales | F Affiliate URL
# G Niche | H Status | I Notes | J Image URL  <-- add this column
SHEET_RANGE = "Inbox!A:M"
COL = {
    "date": 0, "name": 1, "price": 2, "commission": 3, "sales": 4,
    "affiliate_url": 5, "niche": 6, "status": 7, "notes": 8, "image_url": 9,
    "tiktok": 10, "instagram": 11, "shopee_video": 12,
}
STATUS_READY = "Ready"
STATUS_DONE = "Posted"
STATUS_FAILED = "Failed"


@dataclass
class Product:
    row_number: int
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
    bg_color: str = ""      # for cta


@dataclass
class VideoPlan:
    """Full creative plan returned by the scriptwriter."""
    script: str                       # full Thai voiceover
    caption: str
    hashtags: list[str]
    hook_alt_1: str = ""
    hook_alt_2: str = ""
    scenes: list[Scene] = field(default_factory=list)
