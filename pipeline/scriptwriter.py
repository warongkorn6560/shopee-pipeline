"""
Scriptwriter: Claude turns a product into a complete creative plan.

Returns a VideoPlan with:
  - script        : full Thai voiceover (sales-optimized, ~25-30s when spoken)
  - caption        : TikTok caption (Thai + emojis)
  - hashtags       : 5 Thai/EN hashtags
  - hook_alt_1/2   : backup hooks for A/B testing
  - scenes         : assembled timeline (hook AI clip, demo AI clip, benefit, CTA)

The image-to-video prompts are the crucial part: they describe a HUMAN using the
REAL product (the product image is the first frame), in UGC selling style.
"""

from __future__ import annotations

import json

from .config import (
    AI_CLIP_SECONDS, AI_CLIPS, ENV, NICHE, SHOPEE_ORANGE, TIKTOK_HANDLE,
    Product, Scene, VideoPlan,
)

# LLM provider for the script. Default = Vercel AI Gateway (one key, billed via
# your Vercel Pro; swap models with a single string). "anthropic" uses the
# Anthropic SDK directly if you prefer a standalone key.
LLM_PROVIDER = ENV.get("LLM_PROVIDER", "gateway")          # gateway | anthropic
GATEWAY_BASE_URL = ENV.get("LLM_BASE_URL", "https://ai-gateway.vercel.sh/v1")
GATEWAY_MODEL = ENV.get("LLM_MODEL", "google/gemini-2.5-flash-lite")
ANTHROPIC_MODEL = ENV.get("CLAUDE_MODEL", "claude-sonnet-4-6")


def _call_llm(system: str, prompt: str, max_tokens: int = 3000) -> str:
    """Single entry point for the LLM. Returns the raw text response."""
    if LLM_PROVIDER == "anthropic" and ENV.get("ANTHROPIC_API_KEY"):
        import anthropic
        client = anthropic.Anthropic(api_key=ENV["ANTHROPIC_API_KEY"])
        resp = client.messages.create(
            model=ANTHROPIC_MODEL, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text

    # default: Vercel AI Gateway (OpenAI-compatible chat completions)
    import time

    from openai import OpenAI
    key = ENV.get("AI_GATEWAY_API_KEY") or ENV.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError(
            "No LLM key. Set AI_GATEWAY_API_KEY (Vercel AI Gateway) in .env, "
            "or set LLM_PROVIDER=anthropic with ANTHROPIC_API_KEY."
        )
    client = OpenAI(api_key=key, base_url=GATEWAY_BASE_URL)
    # Free-tier gateway is rate-limited; retry with backoff so the daily run survives.
    last = None
    for attempt in range(5):
        try:
            resp = client.chat.completions.create(
                model=GATEWAY_MODEL, max_tokens=max_tokens,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": prompt}],
            )
            return resp.choices[0].message.content
        except Exception as e:  # noqa: BLE001
            last = e
            if "429" in str(e) or "rate" in str(e).lower():
                time.sleep(15 * (attempt + 1))
                continue
            raise
    raise RuntimeError(f"AI Gateway failed after retries: {last}")

SYSTEM = """You are a viral Thai TikTok/Instagram Reels creator who specialises in storytelling-style \
affiliate content. Your videos rack up millions of views because you DON'T make ads — you tell \
short, funny, relatable stories where the product is the hero that saves the day. \
You know every Thai viral format: "มีเพื่อนคนนึง...", "POV:", "เมื่อกี้เพิ่งรู้ว่า...", \
dramatic before-and-after, comedic over-reaction. You reply with raw JSON only."""

PROMPT_TEMPLATE = """Create a VIRAL STORY-FORMAT plan for a {clip_seconds}-second-per-clip vertical (9:16) \
TikTok/Reels video about this product. Goal: maximum shares & comments — NOT a direct ad feel.

PRODUCT
- Name: {name}
- Price: {price} THB
- Commission: {commission}%
- Sales so far: {sales}
- Niche: {niche}
- Notes: {notes}

MANDATORY STORY STRUCTURE for the script:
1. OPEN mid-story with a funny/relatable situation (Thai comedy, NOT a product intro)
2. ESCALATE the problem with exaggeration or a comedic twist
3. PRODUCT enters as the unexpected hero (reveal, not pitch)
4. FUNNY PAYOFF — character's over-the-top happy/shocked reaction
5. SOCIAL PROOF + SOFT CTA ending EXACTLY with: กดลิงก์ใต้คลิปเลย

Viral Thai formats to draw from (pick the best fit for this product):
- "มีเพื่อนคนนึง..." (I have this one friend who...) — 3rd-person comedy distance
- "POV: ..." — viewer IS the character, relatable nightmare scenario
- "เมื่อกี้เพิ่งรู้ว่า..." (I just found out that...) — discovery/revelation shock
- Dramatic contrast: chaos without product vs pure bliss with product
- "ทำไมไม่มีใครบอกฉัน" (why didn't anyone tell me about this) — FOMO guilt trip

Return a JSON object with EXACTLY these keys:
{{
  "script": "Full Thai voiceover, 55-75 words, spoken in ~25-30 seconds. Must be a STORY not a product pitch. Start mid-situation (funny/relatable). Include a comedic beat. Product name appears only ONCE. No emojis. End EXACTLY with: กดลิงก์ใต้คลิปเลย",
  "hook_caption": "On-screen Thai text for the first 3 seconds. <=6 words. The comedy setup — make the viewer NEED to see what happens next.",
  "benefit_captions": ["funny/punchy Thai caption 1 that fits the story moment (<=5 words)", "payoff/reaction Thai caption 2 (<=5 words)"],
  "clip_prompts": [
    {clip_prompt_spec}
  ],
  "caption": "TikTok caption written like a person sharing a funny personal story — Thai, 1-2 emojis, casual tone, price sneaked in naturally, ends with a question to bait comments.",
  "hashtags": ["5 Thai/English hashtags, each starting with #"],
  "hook_alt_1": "Alternative funny story-opening hook in Thai (different format from the main).",
  "hook_alt_2": "Another alternative, even more absurd/dramatic opening hook in Thai."
}}

clip_prompts rules (CRITICAL):
- Exactly {n_clips} prompts, each in ENGLISH.
- The product image is the FIRST FRAME — describe a HUMAN in a story moment with the product naturally in scene.
- A real young Thai person (20s), authentic UGC handheld selfie style, warm natural home lighting, vertical 9:16.
- Clip 1 = the funny STORY moment (character living the relatable problem OR the surprised product reveal).
- Clip 2 = the PAYOFF (character's happy, relieved, or over-the-top delighted reaction with the product).
- One vivid sentence each. No text overlays. Realistic, cheerful, brand-safe — no frustration/distress/danger words.

Output raw JSON only."""


def _clip_prompt_spec(n: int) -> str:
    return ", ".join(
        f'"english motion prompt for clip {i + 1}"' for i in range(n)
    )


def _strip_to_json(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1] if t.count("```") >= 2 else t.strip("`")
        if t.lstrip().lower().startswith("json"):
            t = t.lstrip()[4:]
    # Grab the outermost {...}
    start, end = t.find("{"), t.rfind("}")
    if start != -1 and end != -1:
        t = t[start : end + 1]
    return t.strip()


def write_plan(product: Product) -> VideoPlan:
    prompt = PROMPT_TEMPLATE.format(
        clip_seconds=AI_CLIP_SECONDS,
        name=product.name,
        price=product.price_thb,
        commission=product.commission_pct,
        sales=product.sales or "many",
        niche=product.niche or NICHE,
        notes=product.notes or "-",
        n_clips=AI_CLIPS,
        clip_prompt_spec=_clip_prompt_spec(AI_CLIPS),
    )
    raw = _call_llm(SYSTEM, prompt)
    data = json.loads(_strip_to_json(raw))
    return _assemble_plan(product, data)


def _assemble_plan(product: Product, data: dict) -> VideoPlan:
    """Turn Claude's creative fields into a concrete scene timeline."""
    clip_prompts = data.get("clip_prompts", [])
    if isinstance(clip_prompts, list) and clip_prompts and isinstance(clip_prompts[0], dict):
        # tolerate [{"clip 1": "..."}] shapes
        clip_prompts = [list(d.values())[0] for d in clip_prompts]
    benefit_caps = data.get("benefit_captions", ["", ""])

    scenes: list[Scene] = []
    img = product.image_url

    # Scene 1: hook (AI clip from product image)
    scenes.append(Scene(
        kind="ai" if product.has_image else "kenburns",
        duration=AI_CLIP_SECONDS,
        caption=data.get("hook_caption", ""),
        i2v_prompt=clip_prompts[0] if clip_prompts else "A person excitedly reveals the product, UGC style, warm lighting",
        image_url=img,
    ))

    # Scene 2: demo (second AI clip) if configured and we have an image
    if AI_CLIPS >= 2 and product.has_image and len(clip_prompts) >= 2:
        scenes.append(Scene(
            kind="ai",
            duration=AI_CLIP_SECONDS,
            caption=benefit_caps[0] if benefit_caps else "",
            i2v_prompt=clip_prompts[1],
            image_url=img,
        ))

    # Scene 3: benefit (Ken Burns on the product image, cheap)
    if product.has_image:
        scenes.append(Scene(
            kind="kenburns",
            duration=6,
            caption=benefit_caps[1] if len(benefit_caps) > 1 else f"{product.price_thb} บาท",
            image_url=img,
        ))

    # Scene 4: CTA card (Shopee orange)
    scenes.append(Scene(
        kind="cta",
        duration=5,
        caption=f"{product.price_thb} บาท\\nกดลิงก์ใต้คลิป\\n{TIKTOK_HANDLE}",
        bg_color=SHOPEE_ORANGE,
    ))

    return VideoPlan(
        script=data["script"],
        caption=data.get("caption", ""),
        hashtags=data.get("hashtags", []),
        hook_alt_1=data.get("hook_alt_1", ""),
        hook_alt_2=data.get("hook_alt_2", ""),
        scenes=scenes,
    )


def mock_plan(product: Product) -> VideoPlan:
    """Offline plan (no API) for testing the compositor."""
    return _assemble_plan(product, {
        "script": "สุนัขของคุณกัดของเล่นพังบ่อยไหม ลองเปลี่ยนมาใช้ของเล่นยางกัดทนพิเศษ "
                  "ทำจากยางเกรดดี ปลอดภัย ไม่หลุดเป็นเม็ดโฟม ขายดีหลักพันชิ้น "
                  "รีวิวดีจริง ราคาคุ้มมาก กดลิงก์ใต้คลิปเลย",
        "hook_caption": "หมากัดของพัง?",
        "benefit_captions": ["ยางทนพิเศษ", "ปลอดภัย 100%"],
        "clip_prompts": [
            "A young Thai woman looks frustrated at a chewed-up toy, then smiles holding the new product, UGC handheld, warm home lighting",
            "Close-up of hands giving the rubber chew toy to a happy dog, the dog plays with it, natural light, UGC style",
        ],
        "caption": "ของเล่นหมาทนสุดๆ 99 บาท 🐶 รีบเลยก่อนของหมด!",
        "hashtags": ["#ของเล่นสุนัข", "#ShopeeFinds", "#หมาน่ารัก", "#สัตว์เลี้ยง", "#ของมันต้องมี"],
        "hook_alt_1": "หยุดซื้อของเล่นหมาแบบเดิมได้แล้ว",
        "hook_alt_2": "ของเล่นชิ้นนี้หมาทุกบ้านต้องมี",
    })
