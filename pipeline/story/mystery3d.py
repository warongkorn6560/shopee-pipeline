"""
"mystery3d" style: the same fair-play mystery script as mystery.py, told as a 3D-animated short with a
recurring detective (นักสืบภู and his owl ฮูก) instead of flat noir cards.

Pipeline per episode:
  1. Script — mystery.write_mystery() with this format's notes (≤2 s hook, the detective in every case),
     then the standards editor (writer.write_reviewed_story) like every other style.
  2. Shot list — one LLM call: how each suspect looks + one keyframe and one camera move per beat.
  3. Character sheet — the detective sheet is a fixed asset (assets/mystery3d/detective.png, made once);
     each suspect is drawn per episode in the same style, using the detective sheet as the style reference.
  4. Keyframes — fal image edit with the sheets of everyone in the shot as references, so faces and
     costumes stay the same across shots.
  5. Motion — Kling image-to-video from each keyframe (5 s). The pause beat reuses the last frame.
Rendering (subtitles, evidence tags, countdown, sound) is mystery3d_render.py.
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from ..config import (
    ASSETS, FAL_IMAGE_EDIT_MODEL, FAL_IMAGE_MODEL, FAL_IMAGE_PRICE_USD, FAL_KLING_MODEL,
    FAL_KLING_PRICE_PER_SEC, STORY_3D_CAP_USD,
)
from ..llm import generate_json
from ..video_gen import _ensure_fal_key, _upload_to_fal
from .mystery import MysteryPlan, write_mystery
from .writer import _obj

_S = {"type": "string"}
CLIP_SECONDS = 5
SHEET_DIR = ASSETS / "mystery3d"
DETECTIVE_SHEET = SHEET_DIR / "detective.png"

DETECTIVE = "นักสืบภู"
SIDEKICK = "ฮูก"
DETECTIVE_LOOK = (
    "a Thai private detective around 30 years old, warm brown skin, messy black hair with one stubborn curl "
    "on the forehead, round tortoiseshell glasses, clever calm eyes, a mustard-yellow trench coat over a "
    "charcoal turtleneck, brown leather satchel, holding a small brass pen-light; a small round grey owl "
    "with big amber eyes perched on his left shoulder")
STYLE = (
    "stylized 3D animated feature-film look, appealing characters with expressive eyes and soft "
    "subsurface-scattered skin, cinematic night lighting with warm amber practical lights and cool blue "
    "moonlight, volumetric haze, shallow depth of field, richly detailed set, high-end animation studio "
    "render quality, vertical 9:16 composition")
NO_TEXT = "No written words, letters, numbers, signs, captions or watermarks anywhere in the image."
NEGATIVE = "text, letters, subtitles, watermark, distorted face, morphing, extra fingers, extra limbs, blurry"

FORMAT_NOTES = f"""3D SERIES FORMAT — this channel has a recurring hero:
- "{DETECTIVE}" is a calm, sharp young private detective (not police) with an owl sidekick "{SIDEKICK}". He
  investigates every case; the narrator follows him ("{DETECTIVE}ก้มดูพรม…"). He is never a suspect or the culprit.
- Beat 1 is the HOOK and must land in under 2 seconds: spoken ≤ 24 Thai characters — one concrete, startling
  question or fact ("แหวนหายจากห้องที่ล็อกจากข้างใน?"). No greeting, no series name, no setup.
- Beat 2: {DETECTIVE} arrives at the scene; when, where, what happened.
- Ending beat: {DETECTIVE}'s closing line that lands the twist, then the follow line.
- Keep every beat ≤ 75 spoken Thai characters so each shot stays short and lively.
- Clues must be things a camera can show: objects, marks, a clock, wet shoes, a receipt — so the viewer
  SEES each clue."""

HOOK_MAX_CHARS = 30


def write_mystery3d(topic: str, angle: str = "") -> MysteryPlan:
    """write_mystery with the 3D format notes; retries until the hook fits the 2-second window."""
    notes = (angle + "\n\n" + FORMAT_NOTES).strip()
    for attempt in range(3):
        plan = write_mystery(topic, notes)
        hook = plan.scenes[0].spoken
        if len(hook) <= HOOK_MAX_CHARS:
            plan.style = "mystery3d"
            return plan
        print(f"  [mystery3d] hook too long ({len(hook)} chars, attempt {attempt + 1}): {hook}")
        notes = (angle + "\n\n" + FORMAT_NOTES + f"\n\nThe previous draft's hook was {len(hook)} characters "
                 f"(\"{hook}\"). Beat 1 spoken must be ≤ 24 Thai characters.").strip()
    plan.style = "mystery3d"
    return plan


# ---------------------------------------------------------------------------
# Shot list
# ---------------------------------------------------------------------------

SHOT_SCHEMA = _obj({
    "location": _S,
    "suspect_looks": {"type": "array", "items": _S},
    "shots": {"type": "array", "items": _obj({
        "cast": {"type": "array", "items": {"type": "integer"}},
        "image_prompt": _S, "motion_prompt": _S,
    })},
})

SHOT_SYSTEM = """You are the director of a 3D-animated vertical mystery series. You turn a finished Thai script into
a shot list for an image model (one keyframe per beat) and a video model (one 5-second camera move per beat).
Write prompts in English. The look must feel like a premium animated film, never cheap or generic."""

SHOT_PROMPT = """SCRIPT (JSON): {script}

The recurring detective is {detective} — {look}. Cast index -1 = the detective (with the owl), 0.. = the
suspects in the order given.

Return:
- location: one English sentence describing the single main set (architecture, props, time of night,
  weather, light sources) so every shot is visibly the same place.
- suspect_looks: one per suspect, same order: age, build, face, hair, distinctive outfit with 2 strong
  colours and one signature prop. Everyday Thai people, appealing animated-film characters, clearly
  different silhouettes and colours from each other and from the detective.
- shots: exactly one per beat, same order.
  - cast: who is visible (max 3 indices). Use [] for a pure object close-up.
  - image_prompt: 1-3 sentences: camera angle and lens (close-up, low angle, over-the-shoulder…), who does
    what, expression, the key object, lighting. Refer to people by role ("the detective", "the maid"), not
    by name. Make it cinematic and specific.
  - motion_prompt: one sentence: a camera move plus one small character action (slow push-in, the maid
    glances away nervously…). Keep motion subtle so faces stay stable.

Beat rules:
- Beat 1 (hook): the most striking image of the mystery — the empty spot, the locked door, a shocked face —
  with a fast push-in.
- "suspects" beat: all suspects standing side by side facing camera, LEFT TO RIGHT in the given order,
  full body, even spacing, medium-wide shot. cast = all suspect indices.
- "clue" beats: show the clue object/mark clearly in close-up so the viewer can read it visually; the
  detective's hand or pen-light may point at it.
- "pause" beat: cast [], image_prompt "", motion_prompt "" (it reuses the previous shot).
- "reveal" beats: the culprit in dramatic light, the detective facing them; do not show any clue that was
  not shown before.
- "ending": the detective walking away into the night, owl on his shoulder, or a knowing look to camera.
- Before the reveal, never single out the culprit with lighting or expression more than the others.
- No violence, weapons, blood or children in danger. No text, signs or logos in any shot."""


def shot_list(plan: MysteryPlan) -> dict:
    script = {
        "setting": plan.setting, "suspects": plan.suspects, "culprit_index": plan.answer_suspect,
        "beats": [{"shot": s.visual, "narration": s.narration, "clue": s.card_title, "focus_suspect": s.focus}
                  for s in plan.scenes],
    }
    data = generate_json(SHOT_SYSTEM, SHOT_PROMPT.format(script=json.dumps(script, ensure_ascii=False),
                                                         detective=DETECTIVE, look=DETECTIVE_LOOK),
                         schema=SHOT_SCHEMA, max_tokens=12000, gateway_model="openai/gpt-4.1-mini")
    shots = list(data.get("shots") or [])[:len(plan.scenes)]
    while len(shots) < len(plan.scenes):
        shots.append({"cast": [-1], "image_prompt": "The detective studies the scene, pen-light in hand.",
                      "motion_prompt": "Slow push-in."})
    looks = list(data.get("suspect_looks") or [])
    looks += ["an ordinary Thai adult in simple everyday clothes"] * (len(plan.suspects) - len(looks))
    return {"location": str(data.get("location", "")), "suspect_looks": looks, "shots": shots}


# ---------------------------------------------------------------------------
# fal calls
# ---------------------------------------------------------------------------

def _fal(model: str, args: dict, tries: int = 2) -> dict:
    import fal_client
    for k in range(tries):
        try:
            return fal_client.subscribe(model, arguments=args, with_logs=False)
        except Exception as e:  # noqa: BLE001
            if k == tries - 1:
                raise
            print(f"    [fal] {model} failed ({str(e)[:120]}), retrying…")
            time.sleep(4)
    return {}


def _image(prompt: str, out: Path, refs: list[str] | None = None, aspect: str = "9:16") -> Path:
    args = {"prompt": prompt, "num_images": 1, "output_format": "png", "aspect_ratio": aspect}
    res = _fal(FAL_IMAGE_EDIT_MODEL, {**args, "image_urls": refs}) if refs else _fal(FAL_IMAGE_MODEL, args)
    url = res["images"][0]["url"]
    out.write_bytes(requests.get(url, timeout=120).content)
    return out


def _clip(image_url: str, motion: str, out: Path) -> Path:
    args = {"image_url": image_url, "prompt": f"{motion} Stylized 3D animation, consistent characters.",
            "duration": str(CLIP_SECONDS), "negative_prompt": NEGATIVE, "cfg_scale": 0.5}
    try:
        res = _fal(FAL_KLING_MODEL, args)
    except Exception as e:  # noqa: BLE001 — a flagged motion prompt gets one plain camera move instead
        print(f"    [kling] {str(e)[:120]} — retrying with a plain push-in")
        res = _fal(FAL_KLING_MODEL, {**args, "prompt": "Slow cinematic push-in, subtle ambient motion."}, tries=1)
    url = (res or {}).get("video", {}).get("url")
    if not url:
        raise RuntimeError(f"Kling returned no video: {str(res)[:200]}")
    out.write_bytes(requests.get(url, timeout=180).content)
    return out


def detective_sheet() -> Path:
    """The recurring detective. Made once and kept in assets so every episode shows the same face."""
    if not DETECTIVE_SHEET.exists():
        SHEET_DIR.mkdir(parents=True, exist_ok=True)
        _ensure_fal_key()
        print("  [mystery3d] drawing the detective character sheet (one time)…")
        _image(f"Character design sheet, full body, standing three-quarter view, neutral confident pose: "
               f"{DETECTIVE_LOOK}. Plain dark blue-grey studio backdrop. {STYLE}. {NO_TEXT}",
               DETECTIVE_SHEET, aspect="3:4")
    return DETECTIVE_SHEET


def estimate_usd(plan: MysteryPlan) -> float:
    shots = sum(1 for s in plan.scenes if s.visual != "pause")
    images = len(plan.suspects) + shots + (0 if DETECTIVE_SHEET.exists() else 1)
    return images * FAL_IMAGE_PRICE_USD + shots * CLIP_SECONDS * FAL_KLING_PRICE_PER_SEC


def make_visuals(plan: MysteryPlan, run_dir: Path) -> tuple[dict[int, Path], dict[int, Path], float]:
    """Character sheets → keyframes → Kling clips. Returns ({beat: mp4}, {beat: keyframe png}, fal USD).
    A beat whose clip fails keeps its keyframe (the renderer moves the still)."""
    est = estimate_usd(plan)
    if est > STORY_3D_CAP_USD:
        raise RuntimeError(f"3D visuals would cost ${est:.2f}, over STORY_3D_CAP_USD ${STORY_3D_CAP_USD:.2f}")
    _ensure_fal_key()
    run_dir.mkdir(parents=True, exist_ok=True)
    spent = 0.0 if DETECTIVE_SHEET.exists() else FAL_IMAGE_PRICE_USD
    det_url = _upload_to_fal(detective_sheet())

    shots = shot_list(plan)
    (run_dir / "shot_list.json").write_text(json.dumps(shots, indent=2, ensure_ascii=False))
    print(f"  [mystery3d] shot list ready · location: {shots['location'][:90]}")

    def suspect(k: int) -> str:
        path = run_dir / f"suspect_{k}.png"
        _image(f"Using the reference image ONLY for art style, rendering and lighting (do not copy that person or "
               f"the owl), design a NEW character: {shots['suspect_looks'][k]}. Character design sheet, full body, "
               f"standing three-quarter view, neutral pose, plain dark blue-grey studio backdrop. {STYLE}. "
               f"{NO_TEXT}", path, refs=[det_url], aspect="3:4")
        return _upload_to_fal(path)

    with ThreadPoolExecutor(max_workers=4) as ex:
        sus_urls = list(ex.map(suspect, range(len(plan.suspects))))
    spent += len(sus_urls) * FAL_IMAGE_PRICE_USD
    print(f"  [mystery3d] character sheet: detective + {len(sus_urls)} suspects")

    roles = [f"the {s.get('role') or 'suspect'}" for s in plan.suspects]

    def keyframe(i: int) -> tuple[int, Path, str]:
        shot = shots["shots"][i]
        cast = [c for c in shot.get("cast") or [] if -1 <= c < len(sus_urls)][:3]
        refs, who = [], []
        for c in cast:
            refs.append(det_url if c == -1 else sus_urls[c])
            who.append(f"image {len(refs)} is {'the detective with his grey owl' if c == -1 else roles[c]}")
        cast_line = ("Characters (keep their faces, hair, outfits and colours exactly as in the reference "
                     f"images; {'; '.join(who)})." if refs else
                     "No people in this shot; use the reference image only for art style and lighting.")
        prompt = (f"Cinematic film still. {shot.get('image_prompt', '')} {cast_line} Location: {shots['location']} "
                  f"{STYLE}. {NO_TEXT}")
        path = run_dir / f"key_{i}.png"
        _image(prompt, path, refs=refs or [det_url])
        return i, path, _upload_to_fal(path)

    beats = [i for i, s in enumerate(plan.scenes) if s.visual != "pause"]
    with ThreadPoolExecutor(max_workers=5) as ex:
        keys = list(ex.map(keyframe, beats))
    spent += len(keys) * FAL_IMAGE_PRICE_USD
    stills = {i: p for i, p, _ in keys}
    print(f"  [mystery3d] {len(keys)} keyframes drawn · animating with Kling…")

    def animate(item) -> tuple[int, Path | None]:
        i, _, url = item
        try:
            return i, _clip(url, shots["shots"][i].get("motion_prompt") or "Slow push-in.", run_dir / f"clip_{i}.mp4")
        except Exception as e:  # noqa: BLE001
            print(f"    [kling] beat {i + 1} failed, using the still: {str(e)[:160]}")
            return i, None

    with ThreadPoolExecutor(max_workers=5) as ex:
        done = list(ex.map(animate, keys))
    clips = {i: p for i, p in done if p is not None}
    spent += len(clips) * CLIP_SECONDS * FAL_KLING_PRICE_PER_SEC
    print(f"  [mystery3d] {len(clips)}/{len(keys)} beats animated · fal ${spent:.2f}")
    return clips, stills, round(spent, 3)
