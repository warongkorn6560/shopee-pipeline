"""
Flow A orchestrator: product -> script -> visuals -> voiceover -> compose -> review.

Run:
  python -m pipeline.run                    # next Ready product from the dashboard queue
  python -m pipeline.run --source csv       # from scraper/products.csv (no dashboard)
  python -m pipeline.run --dry-run          # plan only, no render
  python -m pipeline.run --offline          # mock script, no API calls
  python -m pipeline.run --no-publish       # render only: no upload, no Telegram, queue untouched

Every finished video is uploaded to the dashboard's review page and announced
in Telegram with a link to it. VIDEO_PROVIDER=fal (paid, optional) estimates
spend first and aborts above COST_CAP_USD.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import traceback
import unicodedata

from . import compose, hub, llm, products, scriptwriter, video_gen, voiceover
from .config import (
    COST_CAP_USD, ENV, MONTHLY_BUDGET_USD, OUTPUT_DIR, PUBLISH_MODE, VIDEO_PROVIDER, WORK_DIR,
    estimate_video_cost,
)
from .publish import publish, social_caption

SPEND_LOG = OUTPUT_DIR / "spend_log.json"


def _slug(name: str) -> str:
    # Thai vowel/tone marks are category M*, not alnum — keep them with their letters.
    keep = "".join(c if c.isalnum() or unicodedata.category(c).startswith("M") else "_"
                   for c in name)[:40].strip("_")
    return keep or "video"


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def run_url() -> str:
    if ENV.get("GITHUB_RUN_ID"):
        server = ENV.get("GITHUB_SERVER_URL", "https://github.com")
        return f"{server}/{ENV.get('GITHUB_REPOSITORY', '')}/actions/runs/{ENV['GITHUB_RUN_ID']}"
    return ""


def posted_somewhere(result: dict) -> bool:
    return any(isinstance(v, dict) and (v.get("video_id") or v.get("media_id") or v.get("publish_id"))
               for v in result.values())


def _log_spend(name: str, cost: float, mp4: str, flow: str = "shopee") -> float:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    log = json.loads(SPEND_LOG.read_text()) if SPEND_LOG.exists() else []
    log.append({"flow": flow, "name": name, "cost_usd": round(cost, 4), "mp4": mp4, "at": _now_iso()})
    SPEND_LOG.write_text(json.dumps(log, indent=2, ensure_ascii=False))
    month = _now_iso()[:7]
    return sum(e["cost_usd"] for e in log if e["at"][:7] == month)


def run_once(source: str = "platform", dry_run: bool = False, offline: bool = False,
             no_publish: bool = False) -> int:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # Claiming from the dashboard changes the queue, so test modes use the CSV sample.
    live = source == "platform" and not (offline or dry_run or no_publish)
    if source == "platform" and not live:
        print("Test mode: using scraper/products.csv so the dashboard queue is untouched.")
        source = "csv"
    if live and hub.stop_for_budget("Shopee"):
        return 0
    try:
        product = products.get_next_product(source)
    except hub.BudgetStop as e:
        print(f"  ⏸ {e}")
        return 0
    if not product:
        print("No Ready product in the queue. Add or approve products in the dashboard → คิวงาน.")
        return 0
    print(f"▶ Product: {product.name} ({product.price_thb} THB) [{product.ref}]")
    print(f"  renderer: {VIDEO_PROVIDER}")
    if not product.has_image:
        print("  ⚠ no product photo → using a designed product card instead.")

    est = estimate_video_cost()
    print(f"  est. paid-API spend this video: ${est:.2f} (cap ${COST_CAP_USD:.2f})")
    if est > COST_CAP_USD and not offline:
        msg = f"Estimated ${est:.2f} exceeds COST_CAP_USD ${COST_CAP_USD:.2f}. Aborting."
        print("  ✗", msg)
        if live:
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
        if not live:
            print(f"  ✓ rendered (not delivered): {final}")
            return 0

        up = hub.upload_video("shopee", final)
        print(f"  review: {up['reviewUrl']}")
        res = publish(final, plan, product, review_url=up["reviewUrl"])
        print(f"  publish: {res}")
        hub.register_video(
            videoId=up["videoId"], flow="shopee", refId=product.ref, title=product.name,
            pathname=up["pathname"], size=final.stat().st_size, caption=social_caption(plan),
            reviewText=plan.script, link=product.affiliate_url, runUrl=run_url(),
            published=res, status="posted" if posted_somewhere(res) else "review",
            cost={**llm.USAGE, "ttsChars": len(plan.script)},
        )
        products.mark_done(product, source, up["videoId"])
        spent = _log_spend(product.name, est, str(final))
        print(f"  ✓ done ({PUBLISH_MODE}). Month-to-date AI spend: ${spent:.2f} / ${MONTHLY_BUDGET_USD:.0f}")
        return 0

    except Exception as e:
        traceback.print_exc()
        if live:
            products.mark_failed(product, source, f"{type(e).__name__}: {e}")
        return 1


def _silent_voice(path, seconds: float) -> None:
    compose._run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                  "-t", str(seconds), "-q:a", "9", str(path)])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["platform", "csv"], default="platform")
    ap.add_argument("--dry-run", action="store_true", help="plan only, no render")
    ap.add_argument("--offline", action="store_true", help="mock script, silent voice, no API calls")
    ap.add_argument("--no-publish", action="store_true", help="render only; no upload, Telegram, or queue change")
    args = ap.parse_args()
    return run_once(args.source, args.dry_run, args.offline, args.no_publish)


if __name__ == "__main__":
    raise SystemExit(main())
