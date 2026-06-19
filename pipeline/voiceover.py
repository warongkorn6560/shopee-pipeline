"""
Thai voiceover generation. Pluggable across providers.

  elevenlabs : multilingual_v2 (you already have a key; supports Thai)
  azure      : th-TH-PremwadeeNeural (best native Thai prosody, ~free tier)
  fal        : fal.ai TTS models

We synthesize ONE mp3 for the whole script, then the compositor builds the
visual timeline to match its duration. Simpler and more natural than per-scene
sync, and lets captions be timed by proportion.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import requests

from .config import (
    AZURE_VOICE, ELEVENLABS_MODEL, ELEVENLABS_VOICE_ID, ENV, TTS_PROVIDER, WORK_DIR,
)


def _elevenlabs(text: str, out: Path) -> Path:
    key = ENV["ELEVENLABS_API_KEY"]
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    r = requests.post(
        url,
        headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"},
        json={
            "text": text,
            "model_id": ELEVENLABS_MODEL,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.3},
        },
        timeout=120,
    )
    r.raise_for_status()
    out.write_bytes(r.content)
    return out


def _azure(text: str, out: Path) -> Path:
    key = ENV["AZURE_TTS_KEY"]
    region = ENV.get("AZURE_TTS_REGION", "southeastasia")
    url = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"
    ssml = (
        f"<speak version='1.0' xml:lang='th-TH'>"
        f"<voice name='{AZURE_VOICE}'><prosody rate='+8%'>{text}</prosody></voice></speak>"
    )
    r = requests.post(
        url,
        headers={
            "Ocp-Apim-Subscription-Key": key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "audio-24khz-96kbitrate-mono-mp3",
        },
        data=ssml.encode("utf-8"),
        timeout=120,
    )
    r.raise_for_status()
    out.write_bytes(r.content)
    return out


def _fal(text: str, out: Path) -> Path:
    import os
    os.environ["FAL_KEY"] = ENV["FAL_KEY"]
    import fal_client
    result = fal_client.subscribe(
        ENV.get("FAL_TTS_MODEL", "fal-ai/elevenlabs/tts/multilingual-v2"),
        arguments={"text": text, "voice": "Rachel"},
    )
    audio_url = (result or {}).get("audio", {}).get("url") or (result or {}).get("audio_url")
    if not audio_url:
        raise RuntimeError(f"fal TTS returned no audio. Raw: {str(result)[:200]}")
    out.write_bytes(requests.get(audio_url, timeout=120).content)
    return out


def synthesize(text: str, out: Path | None = None, provider: str | None = None) -> Path:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    out = out or (WORK_DIR / "voice.mp3")
    provider = provider or TTS_PROVIDER
    if provider == "azure":
        return _azure(text, out)
    if provider == "fal":
        return _fal(text, out)
    return _elevenlabs(text, out)


def audio_duration(path: Path) -> float:
    """Seconds of an audio/video file, via ffprobe."""
    res = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(res.stdout.strip())
