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
import random
import traceback

from .. import hub, llm, stats, voiceover
from ..config import (
    STORY_CHANNEL_ID, STORY_CHANNEL_PRIMARY, STORY_STYLE, STORY_STYLE_MIX, STORY_THEME,
    COST_CAP_USD, OUTPUT_DIR, PUBLISH_MODE, STORY_AUTO_TOPIC, STORY_IMAGE_PRICE_USD,
    STORY_MAX_AI_IMAGES, STORY_SERIES_NAME, STORY_VOICE_ID, THAI_VOICES, WORK_DIR,
)
from ..publish import publish_story

DOODLE_VOICE_ID = "yq05eeRaHPMGuWTVpqeP"      # Tonce — casual male
from ..run import _log_spend, _silent_voice, _slug, posted_somewhere, run_url
from . import doodle, doodle_render, images, maps, mystery, mystery_render, render, sim, sim_render, topics, writer

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
    social = f"{plan.post_caption}\n\n{tags}"
    if plan.style == "doodle":
        social += f"\n\n📖 {doodle.FICTION}"
        if credits := doodle.credits(plan):
            social += "\n🖼 ภาพพื้นหลัง: " + " · ".join(credits)
    elif plan.style == "mystery":
        social += f"\n\n📖 {mystery.FICTION}"
    elif plan.style == "sim":
        assumptions = " · ".join(getattr(plan, "assumptions", []) or [])
        if assumptions:
            social += f"\n\n🧮 สมมติฐาน: {assumptions}"
        if sources:
            social += f"\n📚 แหล่งข้อมูล: {sources}"
        social += f"\n⚠️ {sim.DISCLAIMER}"
    else:
        credits = [maps.BASEMAP_CREDIT] + sorted({i.credit for i in photos if i.provider == "wikimedia"})
        if sources:
            social += f"\n\n📚 แหล่งข้อมูล: {sources}"
        social += "\n🛰 " + "\n🖼 ".join(credits)
    review = (f"📖 {STORY_SERIES_NAME} — {plan.title}\n\n{social}\n\n"
              f"หัวข้อ: {plan.topic}\nโหมด: {PUBLISH_MODE}")
    return review, social


def _pick_style() -> str:
    """Weighted pick from STORY_STYLE_MIX ("classic:80,reaction:20"); STORY_STYLE forces one."""
    if STORY_THEME == "money":                 # own renderer, no maps or photos
        return "sim"
    if STORY_THEME == "mystery":               # doodle stories; STORY_STYLE=mystery forces the noir puzzle
        return "mystery" if STORY_STYLE == "mystery" else "doodle"
    known = ("classic", "reaction")
    if STORY_STYLE in known:
        return STORY_STYLE
    weights = {}
    for part in STORY_STYLE_MIX.split(","):
        name, _, w = part.partition(":")
        if name.strip() in known:
            try:
                weights[name.strip()] = max(float(w or 0), 0)
            except ValueError:
                pass
    if not sum(weights.values()):
        return "classic"
    return random.choices(list(weights), weights=list(weights.values()))[0]


def _slot_done() -> bool:
    """Scheduled runs only: True when this channel already has a clip since its latest posting slot.
    The workflow keeps a slot due for a few hours because GitHub's hourly cron is often late."""
    import os
    hours = [int(h) for h in os.environ.get("STORY_SLOT_HOURS", "").split(",") if h.strip().isdigit()]
    if os.environ.get("GITHUB_EVENT_NAME") != "schedule" or not hours:
        return False
    bkk = dt.timezone(dt.timedelta(hours=7))
    now = dt.datetime.now(bkk)
    slots = [now.replace(hour=h, minute=0, second=0, microsecond=0) - dt.timedelta(days=d)
             for h in hours for d in (0, 1)]
    slot = max(s for s in slots if s <= now)
    try:
        videos = hub._call("videos-list", {"flow": "story", "days": 2}).get("videos", [])
    except hub.PlatformError:
        return False
    mine = {STORY_CHANNEL_ID} | ({""} if STORY_CHANNEL_PRIMARY else set())
    for v in videos:
        made = dt.datetime.fromisoformat(str(v.get("createdAt", "1970-01-01")).replace("Z", "+00:00"))
        if (v.get("channelId") or "") in mine and made >= slot:
            print(f"  slot {slot:%H:%M} already has a clip ({v.get('title', '')[:40]}) — nothing to do")
            return True
    return False


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
    best, worst = stats.performance()
    if best:
        print(f"  [topics] steering by top performer: {best[0]}")
    topic, angle = writer.propose_topic(previous, best, worst)
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

    if live and not topic_override and _slot_done():
        return 0
    if live and hub.stop_for_budget("คลิปเล่าเรื่อง"):
        return 0
    try:
        topic = _pick_topic(topic_override, live)
    except hub.BudgetStop as e:          # claim said the cap was reached: no auto-topic, no Claude
        print(f"  ⏸ {e}")
        return 0
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
        style = _pick_style()
        print(f"  style: {style}")
        if offline:
            plan = (sim.mock_sim_story(topic.topic) if style == "sim" else
                    mystery.mock_mystery(topic.topic) if style == "mystery" else
                    doodle.mock_doodle(topic.topic) if style == "doodle" else writer.mock_story(topic.topic))
        else:
            plan = writer.write_reviewed_story(topic.topic, topic.angle, style)
        if offline and style not in ("sim", "mystery", "doodle"):
            plan.style = style
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
            narrator = random.choice(list(THAI_VOICES)) if STORY_VOICE_ID == "random" else STORY_VOICE_ID
            speed = None
            if plan.style == "doodle":          # first person "ผม": one casual male voice, a little quicker
                narrator, speed = DOODLE_VOICE_ID, 1.08
            print(f"  narrator: {THAI_VOICES.get(narrator, narrator)}")
            voice, alignment = voiceover.synthesize_with_timestamps(" ".join(texts), voice, narrator, speed=speed)
        audio_len = voiceover.audio_duration(voice)
        durs = scene_durations(texts, alignment, audio_len)
        print(f"  narration {audio_len:.1f}s → beats {[round(d, 1) for d in durs]}")

        out_name = f"story_{_slug(plan.title)}.mp4"
        final = (sim_render.render(plan, durs, voice, run_dir, out_name) if plan.style == "sim" else
                 mystery_render.render(plan, durs, voice, run_dir, out_name) if plan.style == "mystery" else
                 doodle_render.render(plan, durs, voice, run_dir, out_name) if plan.style == "doodle" else
                 render.render(plan, durs, voice, run_dir, out_name, photos))
        review, social = _texts(plan, list(photos.values()))
        (OUTPUT_DIR / "story_latest.json").write_text(json.dumps({
            "topic": plan.topic, "title": plan.title, "mp4": str(final),
            "region": plan.region, "hook": [plan.hook_title, plan.hook_subtitle],
            "scenes": [s.__dict__ for s in plan.scenes],
            "sim": plan.sim.table() if getattr(plan, "sim", None) else None,
            "social_caption": social,
        }, indent=2, ensure_ascii=False))

        if live and plan.style not in ("sim", "mystery", "doodle") and photos:
            # Last gate before anything is posted: look at the finished clip itself.
            from .audit import check_clip
            gate = check_clip(final, plan.title, run_dir / "contact_sheet.jpg")
            print(f"  [gate] bad frames {gate['bad_cells']} — {gate['notes']}")
            if gate["bad_cells"]:
                raise RuntimeError(f"picture check failed, not posted: {gate['notes']}")

        if not live:
            print(f"  ✓ rendered (not delivered): {final}")
            return 0

        up = hub.upload_video("story", final)
        print(f"  review: {up['reviewUrl']}")
        video = dict(
            videoId=up["videoId"], flow="story", refId=topic.ref or "", title=plan.title,
            pathname=up["pathname"], size=final.stat().st_size, caption=social,
            reviewText=plan.narration, sources=plan.sources, runUrl=run_url(),
            cost={**llm.USAGE, "ttsChars": len(plan.spoken)},
            channelId=STORY_CHANNEL_ID, style=plan.style,
        )
        hub.register_video(**video, status="review")
        # Instagram fetches the video from a URL: hand it a short-lived link to our own copy.
        try:
            stored = hub._call("video", {"id": up["videoId"]})
        except hub.PlatformError:
            stored = {}
        res = publish_story(final, f"{review}\n\n▶️ ตรวจในเว็บ: {up['reviewUrl']}", social,
                            video_url=stored.get("url", ""), video_id=up["videoId"], title=plan.title,
                            instagram=stored.get("instagram") if isinstance(stored.get("instagram"), dict) else None)
        print(f"  publish: {res}")
        posted = posted_somewhere(res)
        hub.register_video(**video, published=res, status="posted" if posted else "review")
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
