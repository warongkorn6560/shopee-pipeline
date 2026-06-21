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
    ENV, NICHE, SHOPEE_ORANGE, TIKTOK_HANDLE,
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

SYSTEM = """You are a top-earning Thai TikTok affiliate creator who makes CINEMATIC STORY VIDEOS. \
Your videos go viral because they feel like mini-movies — real situations, real emotions, real person. \
You build tension through 2 problem scenes, release it with a product reveal, then show the happy ending. \
The product is NEVER mentioned until scene 3. สนุก is mandatory. You reply with raw JSON only."""

PROMPT_TEMPLATE = """Create a 4-SCENE STORY VIDEO plan for a Thai TikTok/Reels about this product.
The video tells a STORY in 4 × 5-second scenes — like a mini-movie, not an ad.

PRODUCT
- Name: {name}
- Price: {price} THB
- Commission: {commission}%
- Sales: {sales}
- Niche: {niche}
- Notes: {notes}

THE 4-SCENE STRUCTURE (each scene is exactly 5 seconds):
  Scene 1 — PROBLEM #1: Main character faces a relatable frustrating problem with current solution.
  Scene 2 — PROBLEM #2: Same character, DIFFERENT environment, same problem strikes again (worse).
  Scene 3 — DISCOVERY: Character discovers this product for the first time. Eyes go wide.
  Scene 4 — HAPPY ENDING: Character uses product confidently. Life is better. Big smile, thumbs up.

VOICEOVER SCRIPT RULES:
- Thai, 45-60 words, ~20-25 seconds spoken
- Opens with a relatable problem pain (no product name yet)
- Product name appears ONCE in scene 3 (the discovery)
- Ends EXACTLY with: ดูลิงก์ในโปรไฟล์ได้เลย
- Funny, warm, peer-to-peer tone — like telling a friend a story

CHARACTER RULES (for all Flux/Kling prompts):
- Always: "Thai man in his late 20s, casual t-shirt, authentic UGC style, natural lighting, 9:16 vertical"
- Each scene = different location / environment to show variety
- Expressions must match the moment (frustrated, shocked, amazed, joyful)

Return EXACTLY this JSON:
{{
  "script": "Full Thai voiceover (45-60 words). Story arc: problem → worse problem → discovery → happy ending. Ends with: ดูลิงก์ในโปรไฟล์ได้เลย",
  "story_scenes": [
    {{
      "flux_prompt": "English. Describe the STATIC IMAGE Flux should generate. Thai man in a specific environment with the problem clearly visible. Very detailed: setting, props, expression, lighting. No motion words.",
      "kling_prompt": "English. Describe the MOTION for Kling to animate. What does the character DO in 5 seconds? One vivid action sentence.",
      "caption": "Thai on-screen caption <=5 words. Funny/relatable. No product name."
    }},
    {{
      "flux_prompt": "Scene 2 static image — DIFFERENT location, same problem but worse",
      "kling_prompt": "Scene 2 motion",
      "caption": "Scene 2 Thai caption"
    }},
    {{
      "flux_prompt": "Scene 3 static image — character sees/holds the product for first time, amazed expression",
      "kling_prompt": "Scene 3 motion — character reacts with excitement to discovering the product",
      "caption": "Thai caption that names/hints at the product <=5 words"
    }},
    {{
      "flux_prompt": "Scene 4 static image — character in a beautiful setting confidently using the product, happy",
      "kling_prompt": "Scene 4 motion — character moves freely, smiles big, gives thumbs up to camera",
      "caption": "Thai happy-ending caption <=5 words"
    }}
  ],
  "caption": "Instagram/TikTok caption — Thai, 1-2 emojis, casual story tone, price mentioned naturally, ends with comment-bait question.",
  "hashtags": ["5 Thai/English hashtags starting with #"],
  "hook_alt_1": "Alternative Thai hook for A/B testing (แอบบอก or POV format).",
  "hook_alt_2": "Another alternative hook — more dramatic or absurd."
}}

Output raw JSON only."""


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
        name=product.name,
        price=product.price_thb,
        commission=product.commission_pct,
        sales=product.sales or "many",
        niche=product.niche or NICHE,
        notes=product.notes or "-",
    )
    raw = _call_llm(SYSTEM, prompt)
    data = json.loads(_strip_to_json(raw))
    return _assemble_plan(product, data)


def _assemble_plan(product: Product, data: dict) -> VideoPlan:
    """Turn the LLM's story_scenes into a concrete scene timeline."""
    story_scenes = data.get("story_scenes", [])
    scenes: list[Scene] = []

    for i, s in enumerate(story_scenes[:4]):
        scenes.append(Scene(
            kind="story",
            duration=5,
            caption=s.get("caption", ""),
            flux_prompt=s.get("flux_prompt", ""),
            i2v_prompt=s.get("kling_prompt", ""),
        ))

    # CTA card
    scenes.append(Scene(
        kind="cta",
        duration=5,
        caption=f"{product.price_thb} บาท\nดูลิงก์ในโปรไฟล์ได้เลย\n{TIKTOK_HANDLE}",
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
        "script": "เคยมั้ย อัดคลิปอยู่ดีๆ สายไมค์มันพันไปหมดเลย แล้วยิ่งออกไปอัดข้างนอก สายมันหลุดกลางคลิปเลย จนเจอไมโครโฟนไร้สายตัวนี้ ไม่มีสาย ไม่มีปัญหา ชีวิตดีขึ้นมากเลยนะ ดูลิงก์ในโปรไฟล์ได้เลย",
        "story_scenes": [
            {
                "flux_prompt": "Thai man late 20s at home desk, frustrated with tangled microphone cable around his laptop, messy cables everywhere, confused expression, warm indoor light, UGC style, 9:16 vertical",
                "kling_prompt": "Thai man tries to untangle messy mic cable, gets increasingly frustrated, cable snags on keyboard, he sighs and gives up",
                "caption": "สายไมค์พันกัน 😭",
            },
            {
                "flux_prompt": "Thai man late 20s recording outdoor content at a cafe, wired microphone dangling off his shirt, shocked expression as it falls, people nearby looking, UGC style, 9:16 vertical",
                "kling_prompt": "Mic cable snaps off his shirt mid-recording, he looks down in disbelief, picks it up embarrassed while people glance over",
                "caption": "ไมค์หลุดกลางคลิป 💀",
            },
            {
                "flux_prompt": "Thai man late 20s holding small wireless clip-on microphone, eyes wide open in amazement, product clearly visible, clean background, UGC style, 9:16 vertical",
                "kling_prompt": "Character holds up the tiny wireless mic, eyes go wide with excitement, clips it onto shirt collar easily, no cables anywhere, looks amazed",
                "caption": "เจอตัวนี้แล้ว 😍",
            },
            {
                "flux_prompt": "Thai man late 20s confidently recording outdoors at a park, wireless mic clipped neatly on shirt, big genuine smile, golden hour light, UGC style, 9:16 vertical",
                "kling_prompt": "Character moves freely and energetically while recording, smiles directly at camera, gives enthusiastic thumbs up",
                "caption": "ชีวิตดีขึ้นมากเลย ✨",
            },
        ],
        "caption": "อัดคลิปแล้วสายไมค์พันมาตลอด จนเจอตัวนี้ 🎙️ ไมโครโฟนไร้สาย แค่ 316 บาท เปลี่ยนชีวิตเลยนะ คุณเป็นแบบนี้ด้วยไหม?",
        "hashtags": ["#ไมโครโฟน", "#ShopeeFinds", "#ContentCreator", "#ของมันต้องมี", "#เทคโนโลยี"],
        "hook_alt_1": "แอบบอกว่า content creator ทุกคนต้องมีตัวนี้",
        "hook_alt_2": "POV: สายไมค์หลุดตอนกำลังอัดคลิปสำคัญ",
    })
