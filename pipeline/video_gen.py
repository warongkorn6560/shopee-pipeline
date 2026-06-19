"""
AI motion-clip generation via fal.ai image-to-video.

For each "ai" scene we:
  1. Download the Shopee product image (browser UA to dodge hotlink blocks).
  2. Upload it to fal's own storage -> a fal-hosted URL (so fal's renderer never
     has to fetch a CDN that might 403 — the bug that killed JSON2Video).
  3. Call the configured image-to-video model with the product image as first
     frame + an English motion prompt describing a human using the product.
  4. Download the resulting MP4 into the work dir.

Model + price are set in config (default Kling 2.5 Turbo Pro @ $0.07/s).
"""

from __future__ import annotations

from pathlib import Path

import requests

from .config import ENV, FAL_I2V_MODEL, VIDEO_H, VIDEO_W, WORK_DIR

_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "image/avif,image/webp,image/*,*/*;q=0.8",
}


def _ensure_fal_key() -> None:
    import os
    key = ENV.get("FAL_KEY")
    if not key:
        raise RuntimeError("FAL_KEY missing from .env")
    os.environ["FAL_KEY"] = key


def download_image(url: str, dest: Path) -> Path:
    r = requests.get(url, headers=_BROWSER_HEADERS, timeout=60)
    r.raise_for_status()
    dest.write_bytes(r.content)
    return dest


def _upload_to_fal(local_path: Path) -> str:
    import fal_client
    return fal_client.upload_file(str(local_path))


def _build_args(model: str, prompt: str, image_url: str, seconds: int) -> dict:
    """Different model families want different duration formats / fields."""
    args = {"prompt": prompt, "image_url": image_url}
    if "veo" in model:
        # Veo image-to-video accepts only '4s','6s','8s'; has native audio (off to save).
        valid = min([4, 6, 8], key=lambda v: abs(v - seconds))
        args["duration"] = f"{valid}s"
        args["generate_audio"] = False
        args["auto_fix"] = True   # let Veo auto-rewrite minor content-filter trips
    elif "kling" in model:
        # Kling accepts 5 or 10; derives aspect from the image.
        args["duration"] = "10" if seconds > 7 else "5"
    else:
        # Wan / Seedance / others: integer seconds string.
        args["duration"] = str(seconds)
    return args


def generate_clip(prompt: str, image_url: str, seconds: int, out_path: Path) -> Path:
    """Generate one motion clip. Returns the path to the downloaded MP4."""
    _ensure_fal_key()
    import fal_client

    WORK_DIR.mkdir(parents=True, exist_ok=True)

    # 1-2) localize + re-host the product image on fal (avoids any CDN 403)
    img_local = download_image(image_url, WORK_DIR / "product_src.jpg")
    fal_image_url = _upload_to_fal(img_local)

    # 3) image-to-video with model-appropriate args.
    #    If the prompt trips the content filter, retry once with a safe fallback.
    SAFE_FALLBACK = ("A cheerful young person smiles and holds up the product to the "
                     "camera in a bright cozy home, gentle handheld motion, realistic UGC style")
    args = _build_args(FAL_I2V_MODEL, prompt, fal_image_url, seconds)
    try:
        result = fal_client.subscribe(FAL_I2V_MODEL, arguments=args, with_logs=False)
    except Exception as e:  # noqa: BLE001
        if "content_policy" in str(e) or "content checker" in str(e):
            print("  [video_gen] prompt flagged; retrying with safe fallback prompt…")
            args = _build_args(FAL_I2V_MODEL, SAFE_FALLBACK, fal_image_url, seconds)
            result = fal_client.subscribe(FAL_I2V_MODEL, arguments=args, with_logs=False)
        else:
            raise

    video_url = (result or {}).get("video", {}).get("url")
    if not video_url:
        raise RuntimeError(f"fal returned no video url. Raw: {str(result)[:300]}")

    # 4) download the clip
    r = requests.get(video_url, timeout=180)
    r.raise_for_status()
    out_path.write_bytes(r.content)
    return out_path


def generate_clips(plan, work_dir: Path = WORK_DIR) -> dict[int, Path]:
    """Generate every 'ai' scene's clip. Returns {scene_index: mp4_path}."""
    work_dir.mkdir(parents=True, exist_ok=True)
    clips: dict[int, Path] = {}
    for i, scene in enumerate(plan.scenes):
        if scene.kind != "ai":
            continue
        out = work_dir / f"clip_{i}.mp4"
        print(f"  [video_gen] scene {i}: generating {int(scene.duration)}s clip…")
        generate_clip(scene.i2v_prompt, scene.image_url, int(scene.duration), out)
        clips[i] = out
    return clips
