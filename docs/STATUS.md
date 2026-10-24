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

| | Flow A — Shopee Affiliate | Flow B — ย้อนรอยการเมืองไทย (Thai political history) |
|---|---|---|
| Workflow | `daily-video.yml` 09:00 BKK | `story-video.yml` 19:00 BKK (optional `topic` and `seconds` inputs) |
| Entry point | `python -m pipeline.run` | `python -m pipeline.story` |
| Input | Dashboard queue → products (first `Ready`) | Dashboard queue → stories (first `Ready`); if empty, AI proposes a new topic |
| Script | `pipeline/llm.py`: Claude (`CLAUDE_MODEL`, default claude-opus-5-5) when the `ANTHROPIC_API_KEY` secret exists, else Gemini 2.5 Flash-Lite via AI Gateway | Same LLM switch (else GPT-4.1 mini via Gateway), grounded in fetched Wikipedia text |
| Visuals | Product photo (auto-fetched from the s.shopee short link) + Ken Burns | `story/render.py`: Wikimedia Commons archival photos (archival grade) or designed cards — never AI images; animated พ.ศ. year cards + timeline; satellite-map shots via `maps.py` when a beat needs a place; music `politics_bed.mp3` (`STORY_MUSIC`) |
| Voice | ElevenLabs `eleven_v4`, Thai voice Mali (`SHOP_VOICE_ID`) | ElevenLabs `eleven_v4`, Thai voice Duang (`STORY_VOICE_ID`), TTS-normalized `scene.spoken` text |
| Output | Upload to dashboard → `/review` + Telegram notice | same |
| Cost | $0 per video on AI Gateway; Anthropic per-use pricing once a Claude key is saved | same |

CI setup: both workflows use `.github/actions/setup-media` — a cached static FFmpeg n8.1
build plus apt `libraqm0` only (apt-installing ffmpeg hung runs for 25+ min), and the
Python step fails fast if Pillow can't shape Thai (raqm). Verified 2026-10-24: Flow A
run 40031160778 (38s), Flow B run 40031165981 (67s), both delivered to /review + Telegram.

Flow B content guardrails (legal risk: Criminal Code §112, Computer Crime Act, Meta
political-content rules): prompts put the monarchy/royal family out of scope (reign names
only as time markers, plus the textbook 2475 phrase), no living-politician-centred topics,
no active court cases, topics ≥15 years old, Wikipedia-only facts in a neutral tone.
`writer.write_reviewed_story()` runs a standards-editor pass + one rewrite, and
`writer.royal_term_hits()` is a deterministic keyword backstop; any failure raises
ComplianceError → the run fails closed and the topic is marked Failed. Keep
`STORY_PUBLISH_MODE=review` so a human approves every clip.

Voice note: `eleven_multilingual_v2` has no real Thai support (STT check 65%) —
`eleven_v4` with native Thai voices scores 100%. Thai voices in the ElevenLabs library:
Duang `jucSqawHKM1rUNf78oZQ` (story default), Mali `7XW5JhaNn90bnFojQ5DA` (Flow A
default), Tonce `yq05eeRaHPMGuWTVpqeP`. `story-video.yml` timeout is 40 min (rendering).
Dashboard Settings → "AI & เสียง" saves `ANTHROPIC_API_KEY` as an Actions secret (sealed
box) — the dashboard PAT needs Secrets: Read and write for that.

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

Pipeline ↔ dashboard API: `POST /api/pipeline/{claim,update,stories,upload-url,videos,import,channel-token}`
and `GET|POST /api/pipeline/channels`, with `Authorization: Bearer PIPELINE_API_KEY`
(client: `pipeline/hub.py`). `/api/pipeline` is excluded from the session proxy and authorizes itself.

Channels (`data/channels.json`, `dashboard/lib/channels.ts`): one per Facebook page,
each with its own `theme`, `seriesName`, `niche`, `publishMode`, `enabled`. Settings →
"เพจ & โซเชียล" → เชื่อมเพจ Facebook adds every ticked page in one sign-in (re-connecting
refreshes tokens and keeps settings). Page tokens are AES-GCM sealed with `CHANNEL_KEY`
(Vercel env; falls back to SESSION_SECRET) and only leave via `channel-token`.
Stories may carry `channelId`; unassigned stories belong to the primary channel
(first enabled). `claim {flow:"story", channelId}` only returns that channel's topics;
without `channelId` it acts for the primary. The primary page is still mirrored to the
`FACEBOOK_PAGE_ID` / `FACEBOOK_PAGE_TOKEN` secrets for older runs.

Statuses — products: New → Ready → Producing → Posted / Failed / Hold.
Stories: Ready → Producing → Done / Posted / Failed / Hold. Items stuck in
Producing for 3h are released as Failed. Videos: review → approved / rejected → posted.

## Service and billing audit (2026-10-24)

| Service | Billing | Notes |
|---|---|---|
| ElevenLabs | **Paid** Starter annual (~$50/yr), renews 2027-06-16 | Can't exceed quota → no overage. ~450 chars/video |
| Vercel Pro | **Paid** $20/mo + usage (Jul $33.86, Aug $45.02, Sep $24.82) | Usage is mostly other projects (Sep: thaipography-frontend $4.43); this dashboard doesn't register |
| Vercel Blob `pipeline-data` | Included in Pro | <1 GB with 30-day video cleanup |
| AI Gateway | Free tier (~$5/mo free credit) | Image models blocked on free tier; the LLM used while no Claude key is set |
| Anthropic API (Claude) | **Pay per use — only after a key is saved** (none set on 2026-10-24) | Used by `pipeline/llm.py` when `ANTHROPIC_API_KEY` exists |
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
`STORY_IMAGE_PROVIDER` · `STORY_LLM_MODEL` · `CLAUDE_MODEL` · `STORY_VOICE_ID` · `SHOP_VOICE_ID` ·
`STORY_TARGET_SECONDS`. Unset = the workflow's safe default.
Secrets needed: AI_GATEWAY_API_KEY, ELEVENLABS_API_KEY, TELEGRAM_BOT_TOKEN,
TELEGRAM_CHAT_ID, PIPELINE_API_KEY; optional ANTHROPIC_API_KEY (Claude) and social tokens for auto mode.

## Still needs the user (all optional)

1. Click "เชื่อมเพจ Facebook" in Settings → เพจ & โซเชียล (App secret already saved).
2. Instagram token expired 2026-08-19; TikTok needs OAuth + app audit for public posts.
3. Azure portal check if a card was ever attached.
4. Flow B deliberately uses no AI images (archival photos or cards only).

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
