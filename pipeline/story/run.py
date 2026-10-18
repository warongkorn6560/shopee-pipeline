"""
Flow B orchestrator: topic → story → visuals → narration → compose → publish.

Run:
  python -m pipeline.story                      # next Ready topic from the Sheet
  python -m pipeline.story --topic "…"          # one-off topic (Sheet untouched)
  python -m pipeline.story --dry-run            # print the plan only
  python -m pipeline.story --offline            # mock plan + cards, no API calls
  python -m pipeline.story --no-publish         # render only: no Telegram, no Sheet update
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import traceback

from .. import compose, voiceover
from ..config import (
    COST_CAP_USD, ENV, OUTPUT_DIR, PUBLISH_MODE, STORY_AUTO_TOPIC, STORY_IMAGE_PRICE_USD,
    STORY_MAX_AI_IMAGES, STORY_SERIES_NAME, STORY_VOICE_ID, WORK_DIR, Scene, VideoPlan,
)
from ..publish import publish_story
from ..run import _log_spend, _silent_voice, _slug
from . import images, topics, writer

_MAP_MOTIONS = ("in", "out")
_OTHER_MOTIONS = ("pan-right", "in", "pan-left", "up", "out", "down")


def _run_url() -> str:
    if ENV.get("GITHUB_RUN_ID"):
        server = ENV.get("GITHUB_SERVER_URL", "https://github.com")
        return f"{server}/{ENV.get('GITHUB_REPOSITORY', '')}/actions/runs/{ENV['GITHUB_RUN_ID']}"
    return "local"


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


_MAX_SHOT = 8.5  # seconds a single camera move may hold before it gets stale


def _to_video_plan(plan: writer.StoryPlan, imgs: list[images.SceneImage],
                   durs: list[float]) -> tuple[VideoPlan, list[float]]:
    """Map story scenes to render shots; a long scene becomes two shots on the
    same image with different camera moves so the frame never sits still."""
    scenes, shot_durs, other = [], [], 0
    for i, (sc, img, d) in enumerate(zip(plan.scenes, imgs, durs)):
        parts = 2 if d > _MAX_SHOT else 1
        for part in range(parts):
            if sc.visual == "map":
                motion = _MAP_MOTIONS[(i + part) % 2]
            else:
                motion = _OTHER_MOTIONS[other % len(_OTHER_MOTIONS)]
                other += 1
            scenes.append(Scene(
                kind="kenburns", duration=d / parts, caption=sc.caption,
                image_path=str(img.path), motion=motion, header=plan.title,
                badge=STORY_SERIES_NAME, credit=img.credit, big=(i == 0),
            ))
            shot_durs.append(d / parts)
    return (VideoPlan(script=plan.narration, caption=plan.post_caption,
                      hashtags=plan.hashtags, scenes=scenes), shot_durs)


def _texts(plan: writer.StoryPlan, imgs: list[images.SceneImage]) -> tuple[str, str]:
    tags = " ".join(plan.hashtags)
    sources = " · ".join(plan.sources)
    credits = sorted({i.credit for i in imgs if i.provider == "wikimedia"})
    credit_block = ("\n🖼 " + "\n🖼 ".join(credits)) if credits else ""
    social = f"{plan.post_caption}\n\n{tags}"
    if sources:
        social += f"\n\n📚 แหล่งข้อมูล: {sources}"
    social += credit_block
    review = (f"📖 {STORY_SERIES_NAME} — {plan.title}\n\n{social}\n\n"
              f"หัวข้อ: {plan.topic}\nโหมด: {PUBLISH_MODE}")
    return review, social


def _pick_topic(override: str | None, use_sheet: bool, writes: bool) -> topics.Topic | None:
    """Next topic. With writes=False the Sheet is only read (test renders)."""
    if override:
        return topics.Topic(row_number=None, topic=override, source="cli")
    if not use_sheet:
        return topics.Topic(row_number=None, topic="ทำไมกรีนแลนด์ในแผนที่ดูใหญ่กว่าความจริง", source="cli")
    if writes:
        topics.ensure_tab()
    try:
        t = topics.next_ready()
        previous = topics.previous_topics()
    except Exception:  # noqa: BLE001 — tab may not exist yet in read-only mode
        t, previous = None, []
    if t:
        return t
    if not STORY_AUTO_TOPIC:
        return None
    topic, angle = writer.propose_topic(previous)
    row = topics.append(topic, angle, topics.PRODUCING) if writes else None
    print(f"  [topics] queue empty → auto topic: {topic}")
    return topics.Topic(row_number=row, topic=topic, angle=angle, source="auto")


def run_once(dry_run: bool = False, offline: bool = False, no_publish: bool = False,
             topic_override: str | None = None) -> int:
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = WORK_DIR / "story" / stamp
    run_dir.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    use_sheet = not (offline or topic_override)
    touch_sheet = use_sheet and not (no_publish or dry_run)

    topic = _pick_topic(topic_override, use_sheet, writes=touch_sheet)
    if not topic:
        print("No Ready topic and STORY_AUTO_TOPIC is off. Add a topic (Sheet or dashboard) and retry.")
        return 0
    print(f"▶ Story: {topic.topic} ({topic.source}, row {topic.row_number})")

    est = STORY_MAX_AI_IMAGES * STORY_IMAGE_PRICE_USD
    if est > COST_CAP_USD and not offline:
        print(f"  ✗ Worst-case AI image spend ${est:.2f} exceeds cap ${COST_CAP_USD:.2f}.")
        return 1

    if touch_sheet:
        topics.update(topic.row_number, status=topics.PRODUCING, run=_run_url(), log="")
    try:
        plan = writer.mock_story(topic.topic) if offline else writer.write_story(topic.topic, topic.angle)
        print(f"  title: {plan.title} · {len(plan.scenes)} scenes · {len(plan.narration)} chars")
        if dry_run:
            print(json.dumps({"title": plan.title, "scenes": [s.__dict__ for s in plan.scenes],
                              "post_caption": plan.post_caption, "hashtags": plan.hashtags,
                              "sources": plan.sources}, indent=2, ensure_ascii=False))
            return 0

        if offline:
            imgs = [images.SceneImage(images.globe_card(run_dir / f"card_{i}.jpg",
                                                        highlight=s.highlight, seed=i))
                    for i, s in enumerate(plan.scenes)]
        else:
            imgs = images.fetch_all(plan.scenes, run_dir)

        voice = run_dir / "voice.mp3"
        texts = [s.narration for s in plan.scenes]
        if offline:
            _silent_voice(voice, seconds=max(len(plan.narration) / 9.5, 10))
            alignment = None
        else:
            left = voiceover.remaining_characters()
            if left is not None and left < len(plan.narration):
                raise RuntimeError(f"ElevenLabs quota too low ({left} chars left, need {len(plan.narration)}).")
            voice, alignment = voiceover.synthesize_with_timestamps(" ".join(texts), voice, STORY_VOICE_ID)
        audio_len = voiceover.audio_duration(voice)
        durs = scene_durations(texts, alignment, audio_len)
        print(f"  narration {audio_len:.1f}s → scenes {[round(d, 1) for d in durs]}")

        vplan, shot_durs = _to_video_plan(plan, imgs, durs)
        final = compose.compose(vplan, {}, voice, music=compose.first_music("story"),
                                out_name=f"story_{_slug(plan.title)}.mp4",
                                durations=shot_durs, music_volume=0.08, work_dir=run_dir)
        review, social = _texts(plan, imgs)
        (OUTPUT_DIR / "story_latest.json").write_text(json.dumps({
            "topic": plan.topic, "title": plan.title, "mp4": str(final),
            "scenes": [{**s.__dict__, "image": i.provider, "credit": i.credit}
                       for s, i in zip(plan.scenes, imgs)],
            "social_caption": social,
        }, indent=2, ensure_ascii=False))

        if no_publish:
            print(f"  ✓ rendered (not published): {final}")
            return 0

        res = publish_story(final, review, social)
        print(f"  publish: {res}")
        spent = images.ai_images_used(imgs) * STORY_IMAGE_PRICE_USD
        _log_spend(plan.title, spent, str(final), flow="story")
        posted = any(isinstance(v, dict) and (v.get("video_id") or v.get("media_id") or v.get("publish_id"))
                     for v in res.values())
        summary = " · ".join(f"{k} {'✓' if (v is True or (isinstance(v, dict) and not v.get('error') and not v.get('skipped'))) else '–'}"
                             for k, v in res.items())
        if touch_sheet:
            topics.update(topic.row_number, status=topics.POSTED if posted else topics.DONE,
                          title=plan.title, published=summary, log="")
        print("  ✓ done")
        return 0

    except Exception as e:
        traceback.print_exc()
        if touch_sheet:
            topics.update(topic.row_number, status=topics.FAILED, log=f"{type(e).__name__}: {e}")
        return 1


def main() -> int:
    ap = argparse.ArgumentParser(prog="python -m pipeline.story")
    ap.add_argument("--topic", help="one-off topic; the Sheet is not touched")
    ap.add_argument("--dry-run", action="store_true", help="print the plan only")
    ap.add_argument("--offline", action="store_true", help="mock plan + cards, no API calls")
    ap.add_argument("--no-publish", action="store_true", help="render only; skip Telegram and Sheet updates")
    args = ap.parse_args()
    return run_once(args.dry_run, args.offline, args.no_publish, args.topic)
