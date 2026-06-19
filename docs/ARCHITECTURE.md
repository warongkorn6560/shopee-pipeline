# Architecture — Shopee Affiliate AI-Video Pipeline (v2, code-based)

## Why this replaced the Make.com + JSON2Video stack

The old stack hit two fatal walls:
1. **JSON2Video's renderer 403s on every external video CDN** (Pexels, Google,
   fal). It could only render solid colors / still images — so "real video with
   a human using the product" was impossible.
2. **Make.com's free tier was burned by 15-minute polling** (96 ops/day doing
   nothing) and Core is $9/mo with ops that add up fast.

The v2 pipeline is plain Python + FFmpeg. FFmpeg downloads the AI clips itself,
so there is **no CDN-fetch limitation**. It runs on GitHub Actions for free
(2,000 min/month; a video build takes ~3-5 min).

## Data flow

```
 Google Sheet "Inbox" (Status=Ready, incl. an Image URL column J)
        │  products.py
        ▼
 scriptwriter.py ── Claude ──► Thai sales script + caption + hashtags
        │                        + English image-to-video prompts
        │                        (a real human USING the product)
        ▼
 video_gen.py ── fal.ai image-to-video ──► motion clip(s)
        │   (product image = first frame; re-hosted on fal so no 403)
        ▼
 voiceover.py ── ElevenLabs/Azure ──► Thai voiceover.mp3
        │
        ▼
 compose.py ── FFmpeg ──► 1080x1920 MP4
        │   scenes: [AI hook] [AI demo] [Ken Burns on product] [Shopee CTA]
        │   + Thai captions (Pillow PNG overlays, raqm shaping)
        │   + voiceover (padded) + optional ducked music
        ▼
 publish.py ── Telegram (review)  and/or  upload-post.com (auto)
        │
        ▼
   You: 1 tap to post to TikTok/IG + manual Shopee Video upload (~30s, no API)
```

Orchestrated by `pipeline/run.py`; scheduled daily by
`.github/workflows/daily-video.yml` (cron `0 2 * * *` = 09:00 Bangkok).

## The video (what each one looks like)

~25–35s vertical 9:16, structured to SELL:
1. **Hook (AI clip)** — a real young Thai person reacting to the problem /
   revealing the product. Pattern-interrupt caption.
2. **Demo (AI clip)** — hands using the real product, key benefit shown.
3. **Benefit (Ken Burns)** — slow zoom on the product image + benefit caption
   (cheap; no AI cost).
4. **CTA card** — Shopee-orange screen: price, "กดลิงก์ใต้คลิป", your handle.

Thai voiceover runs across the whole video; captions are timed per scene.

## Cost model (the $30/mo promise)

Per-video variable cost = AI clips only:
`AI_CLIPS × AI_CLIP_SECONDS × FAL_I2V_PRICE_PER_SEC`

| Config | Per video | 30 videos/mo |
|---|---|---|
| 1 clip × 5s × $0.07 (Kling 2.5 Turbo) | $0.35 | **$10.5** |
| 2 clips × 5s × $0.07 | $0.70 | **$21** |
| 2 clips × 5s × $0.05 (Wan 2.5) | $0.50 | **$15** |

Everything else is ~free: Claude script ≈ $0.30/mo total, ElevenLabs free tier,
FFmpeg $0, GitHub Actions $0, Telegram $0. Optional upload-post.com auto-post is
10 free/mo then paid.

**Cost guard:** `run.py` estimates spend before generating and aborts if a single
video would exceed `COST_CAP_USD` (default $1.20). Monthly spend is tracked in
`output/spend_log.json` with a warning near `MONTHLY_BUDGET_USD`.

## Module map

| File | Responsibility |
|---|---|
| `pipeline/config.py` | All tunables, brand, models, prices, `Product`/`Scene`/`VideoPlan` |
| `pipeline/products.py` | Read next Ready product from Sheet/CSV; write status back |
| `pipeline/scriptwriter.py` | Claude → script + i2v prompts + scene timeline |
| `pipeline/video_gen.py` | fal.ai image-to-video; re-hosts product image on fal |
| `pipeline/voiceover.py` | Thai TTS (ElevenLabs/Azure/fal); ffprobe duration |
| `pipeline/captions.py` | Pillow → transparent PNG caption overlays (Thai raqm) |
| `pipeline/compose.py` | FFmpeg scene render + concat + audio mux |
| `pipeline/publish.py` | Telegram delivery + optional upload-post auto-post |
| `pipeline/run.py` | Orchestrator + cost guard + spend log |

## Tunable knobs (env vars)

`PUBLISH_MODE` (review/auto) · `AI_CLIPS` · `AI_CLIP_SECONDS` · `FAL_I2V_MODEL` ·
`FAL_I2V_PRICE_PER_SEC` · `COST_CAP_USD` · `MONTHLY_BUDGET_USD` · `TTS_PROVIDER`.

## What is still manual (honest)

- **Shopee Video upload** — no public API, ever. ~30s in the app per video.
- **Public TikTok auto-post** — TikTok's API needs a 2–6 week app audit for
  public posting. Until then: upload-post.com (10 free/mo) or 1-tap from Telegram.
- **Quality gate** — default `PUBLISH_MODE=review` sends to Telegram first so you
  approve before posting. Flip to `auto` once you trust the output.
