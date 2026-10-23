# CURRENT STATUS / AGENT HANDOFF

**Last verified:** 2026-10-24 (Asia/Bangkok)
**Repository:** `warongkorn6560/shopee-pipeline` · branch `main`
**Dashboard:** https://pipeline-dashboard-seven-kappa.vercel.app (Vercel project `pipeline-dashboard`, code in `dashboard/`, functions in `sin1`)

> New agent: read this file first. `START_HERE.md`, `RUNBOOK.md` and
> `ARCHITECTURE.md` describe the original fal.ai + Google Sheets system and are stale.

## Summary

Two daily video flows run on GitHub Actions. The dashboard is the whole
platform: it holds the queues, receives every finished MP4 for review, and
controls the workflows. Google Sheets is no longer used (the old sheet is kept
as a read-only archive). Telegram only notifies, with a link to the review page.

| | Flow A — Shopee Affiliate | Flow B — เรื่องเล่าจากแผนที่ |
|---|---|---|
| Workflow | `daily-video.yml` 09:00 BKK | `story-video.yml` 19:00 BKK (optional `topic` input) |
| Entry point | `python -m pipeline.run` | `python -m pipeline.story` |
| Input | Dashboard queue → products (first `Ready`) | Dashboard queue → stories (first `Ready`); if empty, AI proposes a new topic |
| Script | Gemini 2.5 Flash-Lite via AI Gateway (free tier) | GPT-4.1 mini via AI Gateway, grounded in fetched Wikipedia text |
| Visuals | Product photo (auto-fetched from the s.shopee short link) + Ken Burns | Real Wikimedia Commons maps/photos with on-screen credits |
| Voice | ElevenLabs multilingual v2 | ElevenLabs with character timestamps |
| Output | Upload to dashboard → `/review` + Telegram notice | same |
| Cost | $0 per video | ≈ $0.005 per video (AI Gateway free credit) |

CI setup: both workflows use `.github/actions/setup-media` — a cached static FFmpeg n8.1
build plus apt `libraqm0` only (apt-installing ffmpeg hung runs for 25+ min), and the
Python step fails fast if Pillow can't shape Thai (raqm). Verified 2026-10-24: Flow A
run 40031160778 (38s), Flow B run 40031165981 (67s), both delivered to /review + Telegram.

Local test flags: `--offline` (no APIs), `--dry-run` (plan only), `--no-publish`
(render with real APIs; queue untouched — Flow A uses `scraper/products.csv`).
Flow B also takes `--topic "…"` (reuses that topic's queue entry if it exists).

## Platform storage (dashboard)

Private Vercel Blob store `pipeline-data` (sin1), connected to the project:

- `data/products.json`, `data/stories.json`, `data/videos.json` — JSON docs,
  written with ETag `ifMatch` (optimistic concurrency) via `dashboard/lib/store.ts`
- `videos/<flow>/<id>.mp4` — uploaded by the pipeline through a presigned PUT
  issued by `/api/pipeline/upload-url`; played back through `/api/videos/<id>`
  (session check → presigned GET). Files older than 30 days are deleted.

Pipeline ↔ dashboard API: `POST /api/pipeline/{claim,update,stories,upload-url,videos,import}`
with `Authorization: Bearer PIPELINE_API_KEY` (client: `pipeline/hub.py`).
`/api/pipeline` is excluded from the session proxy and authorizes itself.

Statuses — products: New → Ready → Producing → Posted / Failed / Hold.
Stories: Ready → Producing → Done / Posted / Failed / Hold. Items stuck in
Producing for 3h are released as Failed. Videos: review → approved / rejected → posted.

## Service and billing audit (2026-10-24)

| Service | Billing | Notes |
|---|---|---|
| ElevenLabs | **Paid** Starter annual (~$50/yr), renews 2027-06-16 | Can't exceed quota → no overage. ~450 chars/video |
| Vercel Pro | **Paid** $20/mo + usage (Jul $33.86, Aug $45.02, Sep $24.82) | Usage is mostly other projects (Sep: thaipography-frontend $4.43); this dashboard doesn't register |
| Vercel Blob `pipeline-data` | Included in Pro | <1 GB with 30-day video cleanup |
| AI Gateway | Free tier (~$5/mo free credit) | Image models blocked on free tier |
| GitHub Actions, Telegram, Wikimedia | Free | |
| Google Sheets / GCP `shopee-pipeline-499816` | Free, billing disabled | No longer used |
| fal.ai | $0, no card | Not used |
| Make.com, JSON2Video | Free plans | v1 leftovers |
| Azure Speech | **Unknown** — needs the user's `az login` / portal check | Not used |

Other charges on the same accounts, unrelated to this system (not touched):
Neon Postgres "Launch" (usage-based, via Vercel) for workwark, lull, firmworks,
claude-app, promschool_2026; Upstash Redis Pay-As-You-Go for 5lab-tokyo-2026;
GCP account warongkorn.most "My Billing Account" (฿0, Gmail SMTP for thaipography/nng).
GCP billing accounts Test / SimilarPlace / My Billing Account 2 were closed and
projects prom-school-map + rugged-research-465212-m4 deleted on 2026-10-24
(restorable until ~2026-11-23).

## GitHub Actions variables (editable from the dashboard)

`PUBLISH_MODE` (A: review|auto) · `LLM_MODEL` · `STORY_PUBLISH_MODE` (B: review|auto) ·
`STORY_SERIES_NAME` · `STORY_NICHE` · `STORY_AUTO_TOPIC` (on|off) ·
`STORY_IMAGE_PROVIDER` · `STORY_LLM_MODEL`. Unset = the workflow's safe default.
Secrets needed: AI_GATEWAY_API_KEY, ELEVENLABS_API_KEY, TELEGRAM_BOT_TOKEN,
TELEGRAM_CHAT_ID, PIPELINE_API_KEY (+ social tokens only for auto mode).

## Still needs the user (all optional)

1. Facebook Page connect for Flow B auto mode (`python -m pipeline.facebook auth`).
2. Instagram token expired 2026-08-19; TikTok needs OAuth + app audit for public posts.
3. Azure portal check if a card was ever attached.
4. Top up AI Gateway credits only if AI illustrations are wanted in Flow B.

## Secrets and local files

Never commit `.env`, `dashboard/.env.local`, service-account JSON, tokens or keys.
`vercel env pull` / `vercel blob create-store` rewrite `dashboard/.env.local` and
drop sensitive values — back it up first. The dashboard password lives in
Vercel env `DASHBOARD_PASSWORD` (a copy is in `dashboard/.env.local`).

Unrelated uncommitted user files — do not commit or discard:
`assets/app_icon.png`, `docs/START_HERE.md`, `assets/character_portrait.jpg`,
`product offers/BatchProductLinks…csv`.

## Useful read-only checks

```bash
gh workflow list --all
gh run list --limit 10
gh secret list
vercel ls pipeline-dashboard
```
