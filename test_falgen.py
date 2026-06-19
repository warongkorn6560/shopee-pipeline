"""One-off: generate Kling vs Veo image-to-video from a sample product image,
send both to Telegram for a quality comparison. Validates the real fal path."""
import os, sys, time
sys.path.insert(0, ".")
from pathlib import Path
import requests
from pipeline.config import ENV, WORK_DIR
from pipeline.video_gen import download_image, _ensure_fal_key

WORK_DIR.mkdir(parents=True, exist_ok=True)
_ensure_fal_key()
import fal_client

# Sample pet-product / lifestyle image (your real runs use each product's own photo)
SAMPLE_IMG = "https://images.unsplash.com/photo-1601758228041-f3b2795255f1?w=1024&q=80"
PROMPT = ("A cheerful young Thai woman sits on her living-room floor and happily plays "
          "with her small dog using the chew toy, the dog bites and tugs it, natural "
          "warm home lighting, authentic UGC handheld phone footage, vertical, realistic")

def tg_video(path, caption):
    with open(path, "rb") as f:
        r = requests.post(
            f"https://api.telegram.org/bot{ENV['TELEGRAM_BOT_TOKEN']}/sendVideo",
            data={"chat_id": ENV["TELEGRAM_CHAT_ID"], "caption": caption},
            files={"video": (Path(path).name, f, "video/mp4")}, timeout=300)
    print("  telegram:", r.json().get("ok"), r.status_code)

print("Downloading + uploading sample image to fal…")
img = download_image(SAMPLE_IMG, WORK_DIR / "sample_product.jpg")
fal_url = fal_client.upload_file(str(img))
print("  fal image url:", fal_url[:70])

jobs = [
    ("Kling 2.5 Turbo (~$0.35)", "fal-ai/kling-video/v2.5-turbo/pro/image-to-video",
     {"prompt": PROMPT, "image_url": fal_url, "duration": "5"}),
    ("Veo 3 (~$1.00, audio off)", "fal-ai/veo3/image-to-video",
     {"prompt": PROMPT, "image_url": fal_url, "duration": "5s", "generate_audio": False}),
]

for label, model, args in jobs:
    print(f"\n=== {label} :: {model} ===")
    try:
        t = time.time()
        res = fal_client.subscribe(model, arguments=args, with_logs=False)
        url = (res or {}).get("video", {}).get("url")
        if not url:
            print("  no video url. raw:", str(res)[:300]); continue
        out = WORK_DIR / (model.split("/")[1] + "_test.mp4")
        out.write_bytes(requests.get(url, timeout=300).content)
        kb = out.stat().st_size // 1024
        print(f"  done in {time.time()-t:.0f}s, {kb}KB -> {out}")
        tg_video(out, f"{label}\nSample product + human using it. {kb}KB")
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")
print("\nALL DONE")
