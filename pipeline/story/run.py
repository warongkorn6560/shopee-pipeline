"""
Flow B orchestrator: topic → story → visuals → narration → compose → review.

Run:
  python -m pipeline.story                      # next Ready topic from the dashboard queue
  python -m pipeline.story --topic "…"          # this topic now (tracked in the queue)
  python -m pipeline.story --dry-run            # print the plan only
  python -m pipeline.story --offline            # mock plan + cards, no API calls
  python -m pipeline.story --no-publish         # render only: no upload, Telegram, or queue change
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import traceback

from .. import hub, voiceover
from ..config import (
    COST_CAP_USD, OUTPUT_DIR, PUBLISH_MODE, STORY_AUTO_TOPIC, STORY_IMAGE_PRICE_USD,
    STORY_MAX_AI_IMAGES, STORY_SERIES_NAME, STORY_VOICE_ID, WORK_DIR,
)
from ..publish import publish_story
from ..run import _log_spend, _silent_voice, _slug, posted_somewhere, run_url
from . import images, maps, render, topics, writer

def scene_durations(texts: list[str], alignment: dict | None, audio_len: float,
                    tail: float = 1.4) -> list[float]:
    """Seconds per scene. Uses the narrator's character timestamps when they
    line up with the text; otherwise splits by character count."""
    joined = " ".join(texts)
    starts, pos = [], 0
    for t in texts:
        starts.append(pos)
        pos += len(t) + 1
    chars = (alignment or {}).get("characters") or []
    st = (alignment or {}).get("character_start_times_seconds") or []
    if chars and len(chars) == len(joined) and len(st) == len(chars):
        marks = [0.0] + [st[i] for i in starts[1:]] + [audio_len]
        durs = [max(marks[i + 1] - marks[i], 0.8) for i in range(len(texts))]
    else:
        weights = [len(t) + 1 for t in texts]
        durs = [audio_len * w / sum(weights) for w in weights]
    durs[-1] += tail
    return durs


def _texts(plan: writer.StoryPlan, photos: list[images.SceneImage]) -> tuple[str, str]:
    tags = " ".join(plan.hashtags)
    sources = " · ".join(plan.sources)
    credits = [maps.BASEMAP_CREDIT] + sorted({i.credit for i in photos if i.provider == "wikimedia"})
    social = f"{plan.post_caption}\n\n{tags}"
    if sources:
        social += f"\n\n📚 แหล่งข้อมูล: {sources}"
    social += "\n🛰 " + "\n🖼 ".join(credits)
    review = (f"📖 {STORY_SERIES_NAME} — {plan.title}\n\n{social}\n\n"
              f"หัวข้อ: {plan.topic}\nโหมด: {PUBLISH_MODE}")
    return review, social


def _pick_topic(override: str | None, live: bool) -> topics.Topic | None:
    """Next topic. Live runs claim it in the dashboard queue; test runs never do."""
    if not live:
        return topics.Topic(ref=None, topic=override or "ทำไมกรีนแลนด์ในแผนที่ดูใหญ่กว่าความจริง", source="cli")
    if override:
        return topics.start(override)
    t, previous = topics.claim()
    if t:
        return t
    if not STORY_AUTO_TOPIC:
        return None
    topic, angle = writer.propose_topic(previous)
    print(f"  [topics] queue empty → auto topic: {topic}")
    return topics.add_auto(topic, angle)


def _summary(res: dict) -> str:
    ok = lambda v: v is True or (isinstance(v, dict) and not v.get("error") and not v.get("skipped"))  # noqa: E731
    return " · ".join(f"{k} {'✓' if ok(v) else '–'}" for k, v in res.items())


def run_once(dry_run: bool = False, offline: bool = False, no_publish: bool = False,
             topic_override: str | None = None) -> int:
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = WORK_DIR / "story" / stamp
    run_dir.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    live = not (offline or dry_run or no_publish)

    topic = _pick_topic(topic_override, live)
    if not topic:
        print("No Ready topic and STORY_AUTO_TOPIC is off. Add a topic in the dashboard → คิวงาน.")
        return 0
    print(f"▶ Story: {topic.topic} ({topic.source}, {topic.ref or 'test'})")

    est = STORY_MAX_AI_IMAGES * STORY_IMAGE_PRICE_USD
    if est > COST_CAP_USD and not offline:
        print(f"  ✗ Worst-case AI image spend ${est:.2f} exceeds cap ${COST_CAP_USD:.2f}.")
        if live:
            topics.update(topic.ref, status=topics.FAILED, lastError="cost cap")
        return 1

    if live:
        topics.update(topic.ref, runUrl=run_url(), lastError="")
    try:
        plan = writer.mock_story(topic.topic) if offline else writer.write_reviewed_story(topic.topic, topic.angle)
        print(f"  title: {plan.title} · {len(plan.scenes)} beats · {len(plan.spoken)} spoken chars")
        if dry_run:
            print(json.dumps({"title": plan.title, "scenes": [s.__dict__ for s in plan.scenes],
                              "post_caption": plan.post_caption, "hashtags": plan.hashtags,
                              "sources": plan.sources}, indent=2, ensure_ascii=False))
            return 0

        photo_idx = [i for i, sc in enumerate(plan.scenes) if sc.visual == "photo"]
        photos: dict[int, images.SceneImage] = {}
        if photo_idx and not offline:
            got = images.fetch_all([plan.scenes[i] for i in photo_idx], run_dir)
            photos = {i: img for i, img in zip(photo_idx, got) if img.provider != "card"}

        voice = run_dir / "voice.mp3"
        texts = [s.spoken or s.narration for s in plan.scenes]
        if offline:
            _silent_voice(voice, seconds=max(len(" ".join(texts)) / 13, 10))
            alignment = None
        else:
            left = voiceover.remaining_characters()
            if left is not None and left < len(plan.spoken):
                raise RuntimeError(f"ElevenLabs quota too low ({left} chars left, need {len(plan.spoken)}).")
            voice, alignment = voiceover.synthesize_with_timestamps(" ".join(texts), voice, STORY_VOICE_ID)
        audio_len = voiceover.audio_duration(voice)
        durs = scene_durations(texts, alignment, audio_len)
        print(f"  narration {audio_len:.1f}s → beats {[round(d, 1) for d in durs]}")

        final = render.render(plan, durs, voice, run_dir, f"story_{_slug(plan.title)}.mp4", photos)
        review, social = _texts(plan, list(photos.values()))
        (OUTPUT_DIR / "story_latest.json").write_text(json.dumps({
            "topic": plan.topic, "title": plan.title, "mp4": str(final),
            "region": plan.region, "hook": [plan.hook_title, plan.hook_subtitle],
            "scenes": [s.__dict__ for s in plan.scenes],
            "social_caption": social,
        }, indent=2, ensure_ascii=False))

        if not live:
            print(f"  ✓ rendered (not delivered): {final}")
            return 0

        up = hub.upload_video("story", final)
        print(f"  review: {up['reviewUrl']}")
        res = publish_story(final, f"{review}\n\n▶️ ตรวจในเว็บ: {up['reviewUrl']}", social)
        print(f"  publish: {res}")
        posted = posted_somewhere(res)
        hub.register_video(
            videoId=up["videoId"], flow="story", refId=topic.ref or "", title=plan.title,
            pathname=up["pathname"], size=final.stat().st_size, caption=social,
            reviewText=plan.narration, sources=plan.sources, runUrl=run_url(),
            published=res, status="posted" if posted else "review",
        )
        topics.update(topic.ref, status=topics.POSTED if posted else topics.DONE, title=plan.title,
                      published=_summary(res), videoId=up["videoId"])
        _log_spend(plan.title, images.ai_images_used(list(photos.values())) * STORY_IMAGE_PRICE_USD, str(final), flow="story")
        print("  ✓ done")
        return 0

    except Exception as e:
        traceback.print_exc()
        if live:
            topics.update(topic.ref, status=topics.FAILED, lastError=f"{type(e).__name__}: {e}")
        return 1


def main() -> int:
    ap = argparse.ArgumentParser(prog="python -m pipeline.story")
    ap.add_argument("--topic", help="make this topic now (added to / taken from the queue)")
    ap.add_argument("--dry-run", action="store_true", help="print the plan only")
    ap.add_argument("--offline", action="store_true", help="mock plan + cards, no API calls")
    ap.add_argument("--no-publish", action="store_true", help="render only; no upload, Telegram, or queue change")
    args = ap.parse_args()
    return run_once(args.dry_run, args.offline, args.no_publish, args.topic)
