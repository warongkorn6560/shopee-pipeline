# CURRENT STATUS / AGENT HANDOFF

**Last verified:** 2026-09-29 (Asia/Bangkok)  
**Repository:** `warongkorn6560/shopee-pipeline`  
**Branch at handoff:** `main` (`09b9c3b` before this document is committed)

> New agent: read this file before doing anything. `docs/START_HERE.md`,
> `docs/RUNBOOK.md`, and `docs/ARCHITECTURE.md` describe the original system but
> are partly stale. Do not enable a workflow or make a paid API call until the
> cost-safe migration below is implemented and tested.

## Executive summary

The project is not currently running on a schedule. Both Shopee workflows are
disabled. The old video design depends on fal.ai, whose credits are exhausted.
The chosen direction is:

1. Keep ElevenLabs for Thai TTS because an annual Starter subscription is
   already paid through 2027-06-16.
2. Stop depending on paid fal.ai generation. Replace it with a zero/low-cost
   product-image + FFmpeg video path before re-enabling automation.
3. Keep Google Sheets as the input source and Telegram as the review channel.
4. Keep publishing in review mode until Instagram and TikTok OAuth are repaired
   and an end-to-end dry run passes.

No one has authorized a new purchase, card, top-up, paid plan, or production
publish. Ask the user immediately before any such action.

## Live service and billing audit

| Service | Access / health | Billing state | Project use / decision |
|---|---|---|---|
| GitHub | CLI logged in as `warongkorn6560`; repo access works | Public-repo Actions are free under normal GitHub limits | Source, Secrets, Pages, Actions |
| ElevenLabs | API verified 2026-09-29; Starter tier; 0/90,000 characters used; next credit reset 2026-10-16 | **Paid annual plan**, renews 2027-06-16; approximately USD 50/year | **Keep and use as default TTS** |
| fal.ai | Key exists; dashboard verified 2026-09-27 | Pay-as-you-go, USD 0 balance, no payment method, auto top-up off; cannot create surprise usage charges in this state | Old Flux/Kling video path is blocked; migrate away instead of topping up |
| Google Cloud | CLI logged in as `warongkorn6560@gmail.com`; project `shopee-pipeline-499816` accessible | `billingEnabled: false`, no billing account attached | Sheets API/service account; retain |
| Google Sheets | Service account and sheet ID are configured; previous scheduled scrape worked | No paid billing currently attached to this GCP project | Product queue/input |
| Telegram | Bot API `getMe` verified 2026-09-29 (`warong_shopee_bot`) | No direct charge | Review notifications; do not send test messages without user approval |
| Instagram / Meta | Local token checked 2026-09-29 and failed with OAuth error 190 | No billing identified | Token expired 2026-08-19; user must approve OAuth again |
| TikTok | Client key/secret names exist in GitHub Secrets | No billing identified | No `TIKTOK_REFRESH_TOKEN`; OAuth still required |
| Azure | `az` CLI installed but `az account show` still requests `az login` | **Unknown until login/audit** | No longer needed for TTS after ElevenLabs switch; audit is optional |
| Vercel | CLI access works as `warongkorn6560` | Separate paid Pro account: USD 16.8229 due in the 2026-09 usage check, mostly other projects | AI Gateway may be used here; Vercel costs are not caused solely by this repo |

### Important cost conclusion

ElevenLabs is not the only paid account overall: Vercel also showed a current
charge, largely for unrelated projects. For this Shopee pipeline, ElevenLabs is
the only already-paid service we intentionally plan to retain. Google Cloud has
billing disabled, and fal.ai cannot charge while it has no balance/payment
method and auto top-up remains off. Azure billing is still unknown because CLI
login has not been completed.

## GitHub workflow state

Verified with `gh workflow list --all` on 2026-09-29:

| Workflow | State |
|---|---|
| `Daily Shopee AI video` | `disabled_manually` |
| `Daily Shopee scrape` | `disabled_inactivity` |
| `pages-build-deployment` | active |

Do not re-enable the video workflow yet. The current committed implementation
still estimates approximately USD 1.40 per video through fal.ai and will fail
because fal has no credits.

## Code changes made locally but not committed at this handoff

These are intentional changes from the latest session:

- `pipeline/config.py`: default `TTS_PROVIDER` changed from `azure` to
  `elevenlabs`.
- `.github/workflows/daily-video.yml`: CI `TTS_PROVIDER` changed from `azure` to
  `elevenlabs`.
- Local `.env`: `TTS_PROVIDER=elevenlabs` (ignored by Git; never commit `.env`).

The Python file passed `python3 -m py_compile`, and the tracked diff passed
`git diff --check`. No paid end-to-end video generation was run.

## Known blockers / required fixes

### 1. Replace the fal.ai video path

Current committed pipeline is:

```text
Google Sheet
  -> Vercel AI Gateway / Gemini script
  -> fal.ai Flux stills + Kling motion (4 x 5 seconds, ~USD 1.40/video)
  -> TTS
  -> Pillow captions + FFmpeg composition
  -> Telegram / social publishing
```

Target cost-safe pipeline:

```text
Google Sheet product image(s)
  -> Gemini script (or deterministic fallback)
  -> local Pillow/FFmpeg scenes, pan/zoom, captions and CTA
  -> ElevenLabs Thai TTS
  -> Telegram review
```

Add an explicit provider/config switch and make the local renderer the safe
default. Keep fal support only as an opt-in provider with a cost cap. Test with
local assets before enabling any schedule.

### 2. TikTok environment loading bug

`.github/workflows/daily-video.yml` passes TikTok variables, but
`pipeline/config.py::load_env()` does not include these real environment
variables in its allowlist:

```text
TIKTOK_CLIENT_KEY
TIKTOK_CLIENT_SECRET
TIKTOK_REFRESH_TOKEN
```

Add them. GitHub Secrets currently contains client key and client secret, but
does **not** contain `TIKTOK_REFRESH_TOKEN`. The user must complete TikTok OAuth
in their logged-in browser; never ask them to paste a password or OTP in chat.

### 3. Instagram OAuth expired

The configured token returns HTTP 400 / OAuthException code 190. Run the
project's Instagram authorization flow after installing dependencies, let the
user approve the browser consent screen, then update local `.env` and the
`INSTAGRAM_ACCESS_TOKEN` GitHub Secret without printing the token into logs or
chat.

### 4. Publishing mode does not match credentials

The workflow defaults `PUBLISH_MODE` to `auto`, but GitHub Secrets does not
currently list `UPLOAD_POST_API_KEY` or `UPLOAD_POST_USER`. Until direct social
OAuth is repaired and tested, use `PUBLISH_MODE=review`. Telegram is working.

### 5. Scraper schedule is inactive

`Daily Shopee scrape` was disabled by GitHub due to inactivity. Inspect the
latest workflow history and inputs before re-enabling it. Re-enabling a free
scrape is separate from re-enabling paid video generation.

### 6. Azure remains unaudited

`az account show` reports: `Please run 'az login'`. If the user wants a complete
Azure billing audit, they must personally accept any Microsoft terms in the
browser and run `az login`. Azure is not required for the chosen TTS stack.

## Credentials and access already available

GitHub Secret **names** verified (values were not read or recorded here):

```text
AI_GATEWAY_API_KEY
AZURE_TTS_KEY
ELEVENLABS_API_KEY
FAL_KEY
GOOGLE_SERVICE_ACCOUNT_JSON
GOOGLE_SHEET_ID
INSTAGRAM_ACCESS_TOKEN        # expired
META_APP_ID
META_APP_SECRET
PUBLISH_MODE
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
TIKTOK_CLIENT_KEY
TIKTOK_CLIENT_SECRET
TTS_PROVIDER
```

Missing for the current publishing implementation:

```text
TIKTOK_REFRESH_TOKEN
UPLOAD_POST_API_KEY
UPLOAD_POST_USER
```

Never commit `.env`, service-account JSON, access tokens, API keys, refresh
tokens, passwords, OTPs, or payment details.

## Working-tree safety

At the time this handoff was written, the repository contained other uncommitted
user files/changes. Do not discard, overwrite, or bundle them into an unrelated
commit:

```text
 M assets/app_icon.png
 M docs/START_HERE.md
?? assets/character_portrait.jpg
?? product offers/BatchProductLinks20260621013517-ab7cd32c8180423e96568d1bf63da82f.csv
```

Also check whether the two intentional ElevenLabs code changes listed above
remain uncommitted before starting work.

## Recommended continuation order

1. Run `git status --short` and read this document.
2. Preserve unrelated dirty files.
3. Commit/test the ElevenLabs default change if it is still pending.
4. Implement the local FFmpeg/product-image video provider and unit/smoke tests.
5. Fix TikTok environment-variable loading.
6. Set safe `PUBLISH_MODE=review` for local and CI runs.
7. Run a local dry run that performs no fal call and sends no public post.
8. Ask the user to complete Instagram/TikTok OAuth consent when the browser is
   ready; store resulting tokens securely.
9. Only after the user reviews a generated MP4, consider enabling the scraper,
   then enable video scheduling separately.

## Useful read-only verification commands

```bash
git status --short
gh auth status
gh workflow list --all
gh secret list
gcloud billing projects describe shopee-pipeline-499816
az account show
vercel whoami
```

Do not use `gh workflow enable` or `gh workflow run` as a mere status check.
