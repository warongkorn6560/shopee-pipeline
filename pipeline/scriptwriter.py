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

SYSTEM = """You are a top-earning Thai TikTok affiliate creator. Your content goes viral because it \
feels like a friend talking — not an ad. You NEVER open with the product. You open with an emotion, \
a problem, or a story hook that stops the scroll. The product appears only at second 15–20 as the \
satisfying answer. สนุก (fun/sanuk) is mandatory in every video — even product content must be \
entertaining. You know every Thai viral format cold. You reply with raw JSON only."""

PROMPT_TEMPLATE = """Create a VIRAL STORY-FORMAT plan for a {clip_seconds}-second-per-clip vertical (9:16) \
TikTok/Reels video about this product. Goal: comments + shares, NOT direct ad feel.

PRODUCT
- Name: {name}
- Price: {price} THB
- Commission: {commission}%
- Sales so far: {sales}
- Niche: {niche}
- Notes: {notes}

TIMING RULES (critical for the algorithm):
- 0–3s   : Hook — pattern interrupt, question, or shock. NEVER show/name the product yet.
- 3–15s  : Build the story/problem. Viewer must feel emotionally invested before product appears.
- 15–20s : Product enters as the satisfying answer/reveal.
- 20–25s : Reaction + social proof (use the sales number naturally).
- 25–30s : CTA — end EXACTLY with: ดูลิงก์ในโปรไฟล์ได้เลย

Choose the BEST format for this product (don't force one):
1. แอบบอก — "แอบบอกว่า..." / "ไม่บอกไม่ได้แล้ว..." → insider secret reveal, triggers curiosity
2. มีเพื่อนคนนึง — 3rd-person proxy story (face-saving Thai storytelling, audience self-inserts)
3. POV — viewer IS the character in a relatable nightmare or discovery moment
4. ใครเป็นแบบนี้บ้าง — relatable complaint → failed alternatives → product as final discovery
5. Before-After result-first — show the AMAZING result in second 1, then explain how

Return a JSON object with EXACTLY these keys:
{{
  "script": "Full Thai voiceover, 55-75 words, ~25-30 seconds spoken. STORY not pitch. Product name appears ONCE around the 15-20s mark. Funny, warm, peer-to-peer tone. No emojis. End EXACTLY with: ดูลิงก์ในโปรไฟล์ได้เลย",
  "hook_caption": "On-screen Thai text overlay for 0–3s. <=6 words. Must make viewer NEED to keep watching — curiosity gap, shock, or relatable pain. NO product name.",
  "benefit_captions": ["punchy story-moment caption 1 (<=5 words, fits the 15-20s product reveal)", "reaction/payoff caption 2 (<=5 words, funny or satisfying)"],
  "clip_prompts": [
    {clip_prompt_spec}
  ],
  "caption": "Instagram/TikTok caption as a peer sharing a funny story — Thai, 1-2 emojis, casual, price mentioned naturally, ends with a question that baits comments (e.g. คุณเป็นแบบนี้ด้วยไหม? / ใครเคยเจอบ้าง?).",
  "hashtags": ["5 Thai/English hashtags starting with #"],
  "hook_alt_1": "Alternative hook in แอบบอก or POV format (different from main hook).",
  "hook_alt_2": "Another alternative — more absurd, dramatic, or funny than hook_alt_1."
}}

clip_prompts rules (CRITICAL):
- Exactly {n_clips} prompts, each in ENGLISH.
- Product image is FIRST FRAME — describe a HUMAN in a story moment, product naturally present.
- Real young Thai person (20s), authentic UGC handheld style, warm home lighting, vertical 9:16.
- Clip 1 = the story/problem moment OR the surprised product-reveal reaction (at ~15-20s story point).
- Clip 2 = the happy payoff — character delighted, relieved, or over-the-top reacting with the product.
- One vivid sentence each. Cheerful, brand-safe. No text overlays, no distress/danger/broken words.

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
