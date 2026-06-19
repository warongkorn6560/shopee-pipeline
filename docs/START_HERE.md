# START HERE — complete hand-off guide

Project folder: `/Users/warongkorn/Documents/works/shopee-pipeline`

---

## What this project does

Turns a Shopee product into a Thai selling video automatically:
1. Reads next product from your Google Sheet (Inbox tab, Status = Ready)
2. Writes a Thai sales script with Gemini via Vercel AI Gateway
3. Generates a 4-second AI video of a human using the product (Google Veo 3 via fal.ai)
4. Records a Thai voiceover (ElevenLabs)
5. Composites everything with FFmpeg: AI clip + Ken Burns + Shopee orange CTA
6. Sends the finished MP4 to your Telegram for you to review before posting

Cost: ~$0.80/video. Budget: $30/month = ~1 video/day covered.

---

## What is already DONE and working

- Full Python pipeline built and tested end-to-end (real video made and sent to Telegram)
- All API keys configured in `.env` (fal.ai, Vercel AI Gateway, ElevenLabs, Telegram)
- Thai caption rendering (Sarabun font + libraqm for correct vowel/tone marks)
- Content-filter safety: auto_fix + safe-fallback prompt retry
- Rate-limit retry (AI Gateway free tier is rate-limited → 5-attempt backoff)
- fal.ai balance: ~$20 loaded, ~$2.35 used so far

---

## What still needs to be done (3 steps)

### Step 1 — Add product images to your Google Sheet (YOU, ~5 min)

Open your sheet:
`https://docs.google.com/spreadsheets/d/1nuxfK86v0X8rP0q58fyqm2gwF4bedOoyMSH6iOwu0aY`

Go to the **Inbox** tab.

- Add header **`Image URL`** in column **J** (if not already there)
- For each product row: open the Shopee listing → right-click the main photo → **Copy image address** → paste in column J
- Set column **B** (Status) to **`Ready`** for any product you want processed

The pipeline reads the first row where Status = Ready.

---

### Step 2 — Connect Google Sheets (Google service account, ~10 min)

The daily robot needs a service account to read your sheet.

**a) Create service account**
1. Go to: https://console.cloud.google.com
2. Select or create a project
3. APIs & Services → Enable APIs → search **Google Sheets API** → Enable
4. APIs & Services → Credentials → **+ Create Credentials** → Service account
5. Name it anything (e.g. `shopee-pipeline`) → Create → Done (skip optional steps)
6. Click the service account email → **Keys** tab → **Add Key** → JSON → Download

**b) Save the file**
```
cp ~/Downloads/your-key-file.json \
   /Users/warongkorn/Documents/works/shopee-pipeline/scraper/service-account.json
```

**c) Share your sheet with the service account**
- Open the downloaded JSON → copy the `client_email` value (looks like `name@project.iam.gserviceaccount.com`)
- Open your Google Sheet → Share → paste that email → set role **Editor** → Send

**d) Test it**
```bash
cd /Users/warongkorn/Documents/works/shopee-pipeline
python -m pipeline.run --source sheets --dry-run
```
Should print the first Ready product without calling any paid API.

---

### Step 3 — Set up daily auto-run on GitHub Actions (~10 min)

This makes the pipeline run every morning at 09:00 Bangkok time, hands-off.

**a) Create a private GitHub repo**
```bash
cd /Users/warongkorn/Documents/works/shopee-pipeline
git init
git add -A
git commit -m "initial"
gh repo create shopee-pipeline --private --source=. --push
```
(Install GitHub CLI first if needed: `brew install gh && gh auth login`)

**b) Add secrets to the repo**

Go to your repo on GitHub → Settings → Secrets and variables → Actions → New repository secret

Add these one by one:

| Secret name | Value (from your `.env`) |
|---|---|
| `FAL_KEY` | your fal.ai key |
| `AI_GATEWAY_API_KEY` | your Vercel AI Gateway key |
| `ELEVENLABS_API_KEY` | your ElevenLabs key |
| `TELEGRAM_BOT_TOKEN` | your Telegram bot token |
| `TELEGRAM_CHAT_ID` | `1165507312` |
| `GOOGLE_SHEET_ID` | `1nuxfK86v0X8rP0q58fyqm2gwF4bedOoyMSH6iOwu0aY` |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | paste the **entire contents** of `scraper/service-account.json` |

**c) Enable Actions**

GitHub repo → Actions tab → click **Enable Actions** if prompted.

The workflow file `.github/workflows/daily-video.yml` is already in the repo.
It runs at `0 2 * * *` UTC = 09:00 Bangkok every day.

**d) Test manually**

GitHub → Actions → `Daily Shopee Video` → **Run workflow** → Run workflow (green button)

Watch the logs. A video should arrive in your Telegram within ~3–5 minutes.

---

## What stays manual forever (no API for these)

- **Shopee Video upload** — Shopee has no upload API. Takes ~30 seconds by hand.
- **Telegram approve** — you tap to approve each video before it posts (intentional safety gate).

---

## Running it manually right now (no sheet needed)

```bash
cd /Users/warongkorn/Documents/works/shopee-pipeline
source .env  # or python-dotenv loads it automatically

# Make a video from a direct image URL:
python -m pipeline.run --source csv
# (edit pipeline/sample_products.csv to change the product)

# Dry run only (no paid APIs called):
python -m pipeline.run --source csv --dry-run

# Offline test (uses a mock plan, no LLM/fal):
python -m pipeline.run --source csv --offline
```

---

## File map

```
shopee-pipeline/
├── .env                          ← all secrets (gitignored)
├── pipeline/
│   ├── config.py                 ← all tunables (model, costs, etc.)
│   ├── scriptwriter.py           ← Gemini via AI Gateway → Thai script
│   ├── video_gen.py              ← fal.ai Veo 3 image-to-video
│   ├── voiceover.py              ← ElevenLabs Thai TTS
│   ├── captions.py               ← Pillow PNG caption overlays
│   ├── compose.py                ← FFmpeg compositor
│   ├── publish.py                ← Telegram delivery
│   └── run.py                    ← main orchestrator
├── scraper/
│   └── service-account.json      ← (you create this in Step 2)
├── assets/fonts/
│   ├── Sarabun-Bold.ttf
│   └── Sarabun-Regular.ttf
├── .github/workflows/
│   └── daily-video.yml           ← GitHub Actions daily cron
├── output/                       ← finished videos land here
└── docs/
    ├── START_HERE.md             ← this file
    ├── ARCHITECTURE.md           ← technical deep-dive
    └── RUNBOOK.md                ← full setup reference
```

---

## Key config values (from `.env`)

```
FAL_I2V_MODEL=fal-ai/veo3/image-to-video   # Google Veo 3 — best "human using product"
AI_CLIPS=1
AI_CLIP_SECONDS=4
FAL_I2V_PRICE_PER_SEC=0.20                  # $0.80/video at 4s
LLM_MODEL=google/gemini-2.5-flash-lite      # free on AI Gateway tier
PUBLISH_MODE=review                         # review = Telegram only (safe)
COST_CAP_USD=1.20                           # abort if cost estimate exceeds this
```

---

## Trigger phrases for the next Claude Code session

- **"set up Google connection"** → walks through Step 2
- **"set up GitHub"** → walks through Step 3
- **"make a video of this: [paste Shopee image URL]"** → makes one video right now
- **"check pipeline status"** → reads spend log and last run output
