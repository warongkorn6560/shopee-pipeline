"""
Flow A orchestrator: product -> script -> visuals -> voiceover -> compose -> publish.

Run:
  python -m pipeline.run                    # one video from the Sheet (real APIs)
  python -m pipeline.run --source csv       # from scraper/products.csv
  python -m pipeline.run --dry-run          # plan only, no render
  python -m pipeline.run --offline          # mock script, no API calls
  python -m pipeline.run --no-publish       # render only: no Telegram, no Sheet update

Safety:
  - VIDEO_PROVIDER=local (default) renders from the product photo with FFmpeg: $0.
  - VIDEO_PROVIDER=fal estimates spend first and aborts if > COST_CAP_USD.
  - Every run's estimated spend is logged to output/spend_log.json.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import traceback
import unicodedata

from . import compose, products, scriptwriter, video_gen, voiceover
from .config import (
    COST_CAP_USD, MONTHLY_BUDGET_USD, OUTPUT_DIR, VIDEO_PROVIDER, WORK_DIR, estimate_video_cost,
)
from .publish import publish

SPEND_LOG = OUTPUT_DIR / "spend_log.json"


def _slug(name: str) -> str:
    # Thai vowel/tone marks are category M*, not alnum — keep them with their letters.
    keep = "".join(c if c.isalnum() or unicodedata.category(c).startswith("M") else "_"
                   for c in name)[:40].strip("_")
    return keep or "video"


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _log_spend(product_name: str, cost: float, mp4: str, flow: str = "shopee") -> float:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    log = json.loads(SPEND_LOG.read_text()) if SPEND_LOG.exists() else []
    log.append({"flow": flow, "name": product_name, "cost_usd": round(cost, 4),
                "mp4": mp4, "at": _now_iso()})
    SPEND_LOG.write_text(json.dumps(log, indent=2, ensure_ascii=False))
    month = _now_iso()[:7]
    return sum(e["cost_usd"] for e in log if e["at"][:7] == month)


def run_once(source: str = "sheets", dry_run: bool = False, offline: bool = False,
             no_publish: bool = False) -> int:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    touch_sheet = source == "sheets" and not no_publish and not dry_run

    product = products.get_next_product(source)
    if not product:
        print("No 'Ready' product found. Mark a row Status=Ready (Sheet or dashboard) and retry.")
        return 0
    print(f"▶ Product: {product.name} ({product.price_thb} THB) row {product.row_number}")
    print(f"  renderer: {VIDEO_PROVIDER}")
    if not product.has_image:
        print("  ⚠ no image URL in column J → using a designed product card instead.")

    est = estimate_video_cost()
    print(f"  est. paid-API spend this video: ${est:.2f} (cap ${COST_CAP_USD:.2f})")
    if est > COST_CAP_USD and not offline:
        msg = f"Estimated ${est:.2f} exceeds COST_CAP_USD ${COST_CAP_USD:.2f}. Aborting."
        print("  ✗", msg)
        if touch_sheet:
            products.mark_failed(product, source, msg)
        return 1

    try:
        plan = scriptwriter.mock_plan(product) if offline else scriptwriter.write_plan(product)
        print(f"  script: {plan.script[:70]}…")
        if dry_run:
            print(json.dumps({
                "script": plan.script, "caption": plan.caption, "hashtags": plan.hashtags,
                "scenes": [{"kind": s.kind, "dur": s.duration, "caption": s.caption,
                            "motion": s.motion} for s in plan.scenes],
            }, indent=2, ensure_ascii=False))
            return 0

        clips = {}
        if VIDEO_PROVIDER == "fal" and not offline:
            clips = video_gen.generate_clips(plan)

        voice = WORK_DIR / "voice.mp3"
        if offline:
            _silent_voice(voice, seconds=20)
        else:
            left = voiceover.remaining_characters()
            if left is not None and left < len(plan.script):
                raise RuntimeError(f"ElevenLabs quota too low ({left} chars left, need {len(plan.script)}).")
            voiceover.synthesize(plan.script, voice)
        print(f"  voiceover: {voice} ({voiceover.audio_duration(voice):.1f}s)")

        final = compose.compose(plan, clips, voice, music=compose.first_music(),
                                out_name=f"{_slug(product.name)}.mp4")

        if no_publish:
            print(f"  ✓ rendered (not published): {final}")
            return 0

        res = publish(final, plan, product)
        print(f"  publish: {res}")
        spent = _log_spend(product.name, est, str(final))
        print(f"  ✓ done. Month-to-date AI spend: ${spent:.2f} / ${MONTHLY_BUDGET_USD:.0f}")
        if touch_sheet:
            products.mark_done(product, source, res)
        return 0

    except Exception as e:
        traceback.print_exc()
        if touch_sheet:
            products.mark_failed(product, source, f"{type(e).__name__}: {e}")
        return 1


def _silent_voice(path, seconds: float) -> None:
    compose._run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                  "-t", str(seconds), "-q:a", "9", str(path)])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["sheets", "csv"], default="sheets")
    ap.add_argument("--dry-run", action="store_true", help="plan only, no render")
    ap.add_argument("--offline", action="store_true", help="mock script, silent voice, no API calls")
    ap.add_argument("--no-publish", action="store_true", help="render only; skip Telegram and Sheet updates")
    args = ap.parse_args()
    return run_once(args.source, args.dry_run, args.offline, args.no_publish)


if __name__ == "__main__":
    raise SystemExit(main())
