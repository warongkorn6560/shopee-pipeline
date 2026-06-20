"""
Orchestrator: product -> script -> AI clips -> voiceover -> compose -> publish.

Run:
  python -m pipeline.run                 # one video from the Sheet (real APIs)
  python -m pipeline.run --source csv    # from scraper/products.csv
  python -m pipeline.run --dry-run       # plan only, no spend (prints the plan)
  python -m pipeline.run --offline       # use mock script + fake clips (no API)

Safety:
  - Estimates fal.ai spend before generating; aborts if > COST_CAP_USD.
  - Logs every run's cost to output/spend_log.json and warns near monthly budget.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import traceback
from pathlib import Path

from . import compose, products, scriptwriter, video_gen, voiceover
from .config import (
    COST_CAP_USD, MONTHLY_BUDGET_USD, OUTPUT_DIR, WORK_DIR, estimate_video_cost,
)
from .publish import publish

SPEND_LOG = OUTPUT_DIR / "spend_log.json"


def _slug(name: str) -> str:
    keep = "".join(c if c.isalnum() else "_" for c in name)[:40].strip("_")
    return keep or "video"


def _log_spend(product_name: str, cost: float, mp4: str) -> float:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    log = json.loads(SPEND_LOG.read_text()) if SPEND_LOG.exists() else []
    log.append({"name": product_name, "cost_usd": round(cost, 4),
                "mp4": mp4, "at": _now_iso()})
    SPEND_LOG.write_text(json.dumps(log, indent=2, ensure_ascii=False))
    month = _now_iso()[:7]
    spent = sum(e["cost_usd"] for e in log if e["at"][:7] == month)
    return spent


def _now_iso() -> str:
    # GitHub Actions / cron supply real time; local runs use system clock.
    return dt.datetime.utcnow().isoformat()


def run_once(source: str = "sheets", dry_run: bool = False, offline: bool = False) -> int:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1) next product
    product = products.get_next_product(source)
    if not product:
        print("No 'Ready' product found. Add a row (Status=Ready) and retry.")
        return 0
    print(f"▶ Product: {product.name} ({product.price_thb} THB) row {product.row_number}")
    if product.has_image:
        print(f"  image: {product.image_url[:80]}")
    else:
        print("  ⚠ no image URL → will fall back to text card scenes (lower fidelity).")

    # 2) cost guard
    est = estimate_video_cost()
    print(f"  est. fal.ai spend this video: ${est:.2f} (cap ${COST_CAP_USD:.2f})")
    if est > COST_CAP_USD and not offline:
        msg = f"Estimated ${est:.2f} exceeds COST_CAP_USD ${COST_CAP_USD:.2f}. Aborting."
        print("  ✗", msg)
        if source == "sheets":
            products.mark_failed(product, source, msg)
        return 1

    try:
        # 3) script + plan
        plan = scriptwriter.mock_plan(product) if offline else scriptwriter.write_plan(product)
        print(f"  script: {plan.script[:70]}…")
        if dry_run:
            print(json.dumps({
                "script": plan.script, "caption": plan.caption,
                "hashtags": plan.hashtags,
                "scenes": [{"kind": s.kind, "dur": s.duration,
                            "caption": s.caption, "i2v": s.i2v_prompt} for s in plan.scenes],
            }, indent=2, ensure_ascii=False))
            return 0

        # 4) AI clips
        if offline:
            clips = {i: WORK_DIR / f"clip_{i}.mp4" for i, s in enumerate(plan.scenes) if s.kind == "ai"}
        else:
            clips = video_gen.generate_clips(plan)

        # 5) voiceover
        voice = (WORK_DIR / "voice.mp3")
        if not offline:
            voiceover.synthesize(plan.script, voice)
        print(f"  voiceover: {voice} ({voiceover.audio_duration(voice):.1f}s)")

        # 6) compose
        out_name = f"{_slug(product.name)}.mp4"
        final = compose.compose(plan, clips, voice, music=compose.first_music(), out_name=out_name)

        # 7) publish
        res = publish(final, plan, product)
        print(f"  publish: {res}")

        # 8) bookkeeping
        spent = _log_spend(product.name, est, str(final))
        print(f"  ✓ done. Month-to-date AI spend: ${spent:.2f} / ${MONTHLY_BUDGET_USD:.0f}")
        if spent > MONTHLY_BUDGET_USD * 0.9:
            print(f"  ⚠ Near monthly budget (${spent:.2f}/${MONTHLY_BUDGET_USD:.0f}).")
        if source == "sheets":
            products.mark_done(product, source, res)
        return 0

    except Exception as e:
        traceback.print_exc()
        if source == "sheets":
            products.mark_failed(product, source, f"{type(e).__name__}: {e}")
        return 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["sheets", "csv"], default="sheets")
    ap.add_argument("--dry-run", action="store_true", help="plan only, no spend")
    ap.add_argument("--offline", action="store_true", help="mock script + fake clips")
    args = ap.parse_args()
    return run_once(args.source, args.dry_run, args.offline)


if __name__ == "__main__":
    raise SystemExit(main())
