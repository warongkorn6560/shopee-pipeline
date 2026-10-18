# CURRENT STATUS / AGENT HANDOFF

**Last verified:** 2026-10-19 (Asia/Bangkok)
**Repository:** `warongkorn6560/shopee-pipeline` · branch `main`
**Dashboard:** https://pipeline-dashboard-seven-kappa.vercel.app (Vercel project `pipeline-dashboard`, code in `dashboard/`)

> New agent: read this file first. `START_HERE.md`, `RUNBOOK.md` and
> `ARCHITECTURE.md` describe the original fal.ai system and are stale.

## Summary

Two daily video flows run on GitHub Actions, both in **review mode** (the MP4
and a ready-to-paste caption go to the Telegram review chat; nothing posts
publicly until a publish-mode variable is switched to `auto`).

| | Flow A — Shopee Affiliate | Flow B — เรื่องเล่าจากแผนที่ |
|---|---|---|
| Workflow | `daily-video.yml` 09:00 BKK (+ `scrape.yml` 08:30) | `story-video.yml` 19:00 BKK (optional `topic` input) |
| Entry point | `python -m pipeline.run` | `python -m pipeline.story` |
| Input | Sheet tab `Inbox`, first row with Status=Ready | Sheet tab `Stories`, first Ready row; if empty, AI proposes a new topic |
| Script | Gemini 2.5 Flash-Lite via AI Gateway (free tier) | GPT-4.1 mini via AI Gateway, grounded in fetched Wikipedia text |
| Visuals | Product photo (column J) + Ken Burns; card if no photo | Real Wikimedia Commons maps/photos (PD/CC0/CC BY/BY-SA, credited on screen); globe cards as fallback |
| Voice | ElevenLabs multilingual v2 | ElevenLabs with character timestamps → exact scene timing |
| Cost | $0 per video | ≈ $0.005 per video (AI Gateway free monthly credit) |
| Auto-publish | TikTok / Instagram / upload-post | Facebook Page Reels (+ TikTok / Instagram) |

Local test flags (both entry points): `--offline` (no APIs), `--dry-run`
(plan only), `--no-publish` (render with real APIs, no Telegram, no Sheet
writes). Flow B also takes `--topic "…"`.

## Service and billing audit

| Service | Billing | Notes |
|---|---|---|
| ElevenLabs | **Paid** Starter annual (~$50/yr), renews 2027-06-16 | 90,000 chars/month, cannot be extended → no overage charges. Both flows use ~450 chars/video |
| Vercel | **Paid** Pro (Sep 2026 usage $16.82, mostly other projects) | Hosts the dashboard; AI Gateway is on the free tier (~$5/month free credit; image models blocked) |
| GitHub Actions | Free (public repo) | |
| Google Cloud / Sheets | Free — billing disabled on `shopee-pipeline-499816` | |
| Telegram | Free | bot `@warong_shopee_bot` |
| Wikimedia / Wikipedia | Free | attribution handled automatically |
| fal.ai | $0 balance, no card, auto top-up off | Only used if `VIDEO_PROVIDER=fal` |
| Make.com | Free plan (verified via API 2026-10-19) | v1 leftover, unused |
| JSON2Video | Free plan (verified via API 2026-10-19) | v1 leftover, unused |
| Azure Speech | **Unknown** — `az login` never completed | Not used anymore; user should check the Azure portal if a card was ever attached |
| upload-post.com | Free tier, keys only in local `.env` | Optional, Flow A auto mode |

## GitHub Actions variables (editable from the dashboard)

`PUBLISH_MODE` (A: review|auto) · `VIDEO_PROVIDER` (A: local|fal) · `LLM_MODEL` ·
`STORY_PUBLISH_MODE` (B: review|auto) · `STORY_SERIES_NAME` · `STORY_NICHE` ·
`STORY_AUTO_TOPIC` (on|off) · `STORY_IMAGE_PROVIDER` (auto|wikimedia|gateway|cards) ·
`STORY_LLM_MODEL`. Unset = the workflow default (always the safe value).

## Still needs the user

1. **`GITHUB_TOKEN` for the dashboard** — fine-grained PAT on this repo only
   (Actions RW, Variables RW, Secrets R, Contents R) added in Vercel env, then
   redeploy. Without it the dashboard shows queues, quotas and billing but
   cannot run workflows or edit settings. Agents cannot create PATs.
2. **Facebook Page** (only for Flow B auto mode): add "Facebook Login for
   Business" to the Meta app with redirect
   `https://warongkorn6560.github.io/shopee-pipeline/`, then
   `python -m pipeline.facebook auth` (saves `FACEBOOK_PAGE_ID/TOKEN` secrets).
3. Instagram token expired 2026-08-19 (`python -m pipeline.instagram auth`);
   TikTok has no refresh token (`python -m pipeline.tiktok auth`; public posting
   needs TikTok's app audit).
4. Optional: top up AI Gateway credits to enable AI illustrations in Flow B.

## Secrets and local files

Never commit `.env`, `dashboard/.env.local`, service-account JSON, tokens or
keys. The local `.env` now has `PUBLISH_MODE=review` (was `auto`).
The dashboard's local password lives in `dashboard/.env.local`
(`DASHBOARD_PASSWORD`, same value as in Vercel); change it in Vercel any time.

Unrelated uncommitted user files — do not commit or discard:
`assets/app_icon.png`, `docs/START_HERE.md`, `assets/character_portrait.jpg`,
`product offers/BatchProductLinks…csv`.

## Useful read-only checks

```bash
gh workflow list --all
gh run list --limit 10
gh secret list
gh variable list
```
