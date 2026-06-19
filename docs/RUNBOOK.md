# Runbook — setup, daily use, debugging

## 0. What you must give me (API KEYS) — when you're ready

Paste each into `.env`. **Don't paste into chat if you prefer — just say the word
and I'll walk you to each dialog.** Required vs optional:

| Key | Required? | Where to get it | Cost |
|---|---|---|---|
| `FAL_KEY` | ✅ REQUIRED | https://fal.ai/dashboard/keys | pay-as-you-go (~$10–21/mo at 1/day) |
| `AI_GATEWAY_API_KEY` | ✅ REQUIRED | Vercel dashboard → AI Gateway → API Keys | billed via your Vercel Pro (~$0.30/mo) |
| `ELEVENLABS_API_KEY` | ✅ (already have, paid) | — | your subscription |
| `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` | ✅ (already set) | — | free |
| Google **service account JSON** | ✅ REQUIRED | see step 2 below | free |
| `UPLOAD_POST_API_KEY` + `UPLOAD_POST_USER` | ⬜ optional (auto-post) | https://www.upload-post.com | 10 free/mo, then paid |
| `AZURE_TTS_KEY` + `AZURE_TTS_REGION` | ⬜ optional (better Thai voice) | Azure Portal → Speech | free tier |
| `ANTHROPIC_API_KEY` | ⬜ optional (only if `LLM_PROVIDER=anthropic`) | console.anthropic.com | — |

The script LLM goes through **Vercel AI Gateway** by default (`LLM_PROVIDER=gateway`,
`LLM_MODEL=anthropic/claude-sonnet-4.6`). Swap `LLM_MODEL` to any gateway model
(e.g. `google/gemini-3.1-flash` for near-$0, `openai/gpt-5.5`) with no code change.

That's **1 new paid key** (fal.ai) + your **Vercel AI Gateway** key + a free Google
service account. Everything else you already have.

## 1. Local install (one time)

```bash
cd shopee-pipeline
brew install ffmpeg libraqm           # macOS (Linux: apt install ffmpeg libraqm0)
pip install -r requirements.txt
# (optional, for perfect Thai shaping on mac) rebuild Pillow against libraqm:
#   PKG_CONFIG_PATH="$(brew --prefix)/lib/pkgconfig" pip install --no-binary :all: --force-reinstall Pillow
```

## 2. Google service account (so the daily job can read the Sheet)

1. https://console.cloud.google.com → create/choose a project.
2. APIs & Services → Enable **Google Sheets API**.
3. IAM → Service Accounts → Create → **Keys → Add key → JSON** → download.
4. Save it as `scraper/service-account.json`.
5. Open the Sheet → Share → add the service account's email (…@….iam.gserviceaccount.com)
   as **Editor**.

## 3. Add the Image URL column to the Sheet

The "real product in the video" comes from the product's image. In the **Inbox**
tab add a header **Image URL** in column **J**. For each product, paste the main
Shopee product image URL (right-click the product photo → Copy image address).
Set **Status (col H) = Ready** for products you want made into videos.

> No image? The pipeline still runs but falls back to text-card scenes (lower
> fidelity). For best results, always include an image URL.

## 4. Test without spending money

```bash
python -m pipeline.run --source csv --offline   # mock script + fake clips, real compose+Telegram
python -m pipeline.run --dry-run                # real Claude plan only (tiny cost), no video
```

## 5. First real video

```bash
python -m pipeline.run --source sheets          # picks the next Ready row
```
Watch Telegram for the MP4 + caption + hashtags + affiliate link. Review it.

## 6. Go daily (free scheduler)

1. Push this repo to GitHub (private).
2. Repo → Settings → Secrets and variables → Actions → add secrets:
   `FAL_KEY`, `ANTHROPIC_API_KEY`, `ELEVENLABS_API_KEY`, `TELEGRAM_BOT_TOKEN`,
   `TELEGRAM_CHAT_ID`, `GOOGLE_SHEET_ID`, `GOOGLE_SERVICE_ACCOUNT_JSON` (paste the
   whole JSON), and optionally `UPLOAD_POST_API_KEY`, `UPLOAD_POST_USER`.
3. (Optional) Variables: `PUBLISH_MODE=auto`, `AI_CLIPS`, `FAL_I2V_MODEL`.
4. Actions tab → "Daily Shopee AI video" → Run workflow (test), then it runs daily
   at 09:00 Bangkok.

## Dialing cost vs quality

- Tighter budget: set `AI_CLIPS=1` (~$10.5/mo) or `FAL_I2V_MODEL=fal-ai/wan/v2.5/image-to-video`.
- Max quality: `AI_CLIPS=2`, keep Kling; or try Seedance for reference-to-video.
- The cost guard (`COST_CAP_USD`) blocks any video that would overspend.

## Debugging

| Symptom | Fix |
|---|---|
| `FAL_KEY missing` | add it to `.env` / GitHub secret |
| fal returns no video url | model name wrong → check `FAL_I2V_MODEL`; see fal dashboard logs |
| Thai text marks misaligned | libraqm not active → `features.check('raqm')` should be True; see step 1 |
| Telegram video fails (>50MB) | shorten clips (`AI_CLIP_SECONDS`) or lower resolution |
| "No 'Ready' product found" | set a row's Status=Ready in the Inbox tab |
| Aborted on cost cap | lower `AI_CLIPS` or raise `COST_CAP_USD` deliberately |

## Spend tracking

Every run appends to `output/spend_log.json`. Month-to-date AI spend is printed at
the end of each run and warns past 90% of `MONTHLY_BUDGET_USD`.
