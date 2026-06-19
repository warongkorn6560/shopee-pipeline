# Shopee Affiliate TikTok Pipeline

Fully-automated content factory: pet products → script → voice → video → Telegram.
Built on Make.com + Anthropic + ElevenLabs + JSON2Video + Telegram.

> Architecture diagram & module-name cheatsheet: [`architecture.md`](./architecture.md)

## What's deployed

- **Make.com scenario 5048310** — "Shopee Affiliate Video Pipeline"
  - URL: https://us2.make.com/2282352/scenarios/5048310/edit
  - 9 modules, active, polling Inbox every 15min
- **Telegram bot** — `@warong_shopee_bot` (token in `.env`)
- **Google Sheet** — `1nuxfK86v0X8rP0q58fyqm2gwF4bedOoyMSH6iOwu0aY`
- **Python scraper** — `scraper/scrape_shopee.py` (CSV mode works; live-API mode needs anti-bot lift)

## Status: ready to run

Verified via Make REST API:
- Scenario is **active**, not paused, not invalid, scheduler ON
- Both Google Sheets modules bound to connection 8842825 (your account)
- Anthropic module on Make's built-in token (no extra setup)
- All HTTP modules have keys injected from `.env`
- Telegram bot delivered a test message (msg_id 2)

### To trigger your first real video

The `watchRows` trigger only fires for **new** rows added after the last poll. Pick one:

- **Easiest** — Open the [Inbox tab](https://docs.google.com/spreadsheets/d/1nuxfK86v0X8rP0q58fyqm2gwF4bedOoyMSH6iOwu0aY/edit#gid=0)
  and add one row with: `today's date | Product Name | Price | 45 | 100 | https://shopee.co.th/... | Pet supplies & toys | New | notes`.
  Wait ≤15 min, or open the scenario and click **Run once** to bypass the poll wait.
- **Faster smoke test** — Open the scenario at https://us2.make.com/2282352/scenarios/5048310/edit,
  click the trigger module (Watch Rows) → "Choose where to start" → "From now on", save.
  Then add a row.

### Heads-up for the first run

- If module 6 (JSON2Video) returns 401, the API key wasn't injected — re-run `bash upload.sh`.
- Module 2 may say "JSON parse failed" if Claude wraps output in ```json fences. If you
  see this in execution history, wrap the SetVariables `parseJSON()` calls with a
  `replace()` to strip the fences (see Debugging below).
- JSON2Video free tier = ~52 sec render quota left. First test will work; second will fail
  with quota exceeded until next month. Upgrade plan or wait.

## Daily flow (after one-time setup)

```
Option A — manual product entry (immediate):
  Open Google Sheet → Inbox tab → add a row with: Product Name, Price, Commission%,
  Sales, Affiliate URL, Niche, "New", optional notes.
  Make polls every 15min; full video lands in Telegram ~3 min after trigger.

Option B — scripted bulk add (CSV from scraper):
  cd /Users/warongkorn/Documents/works/shopee-pipeline
  cp scraper/products.csv.example scraper/products.csv  # then edit with your products
  python3 scraper/scrape_shopee.py --source csv --csv scraper/products.csv --sink sheets
  (requires Google service account JSON — see scraper/README below)

Option C — live Shopee scrape (experimental):
  Shopee returns 403 to plain requests. Either:
    - install curl_cffi:  pip install curl-cffi   then patch fetch_shopee_candidates
      to use curl_cffi.requests.get(..., impersonate="chrome120")
    - OR use playwright with stealth + paste your Shopee session cookies.
```

## How to add new products manually

The fastest path for now: **fill out the Inbox tab in the Google Sheet**.
Columns A–I in order:
`Date | Product Name | Price (THB) | Commission % | Sales | Affiliate URL | Niche | Status | Notes`

Within 15 minutes (the watcher's poll interval), the scenario will pick it up.
To skip the wait, click "Run once" in the scenario header.

## Debugging

### Telegram message didn't arrive
Open scenario → History → click the last execution → expand each module. Look for:
- Module 2 (Claude) returned non-JSON → Claude got verbose; tighten the prompt.
- Module 3 (Set Variables) parseJSON errored → Claude wrapped the JSON in ```json fences;
  add `replace(2.result; "```json"; ""); "```"; "")` around parseJSON.
- Module 6 (JSON2Video) returned 401 → API key didn't get injected; re-run `bash upload.sh`.
- Module 8 (status check) showed `status: "processing"` → render took >60s; bump the
  sleep in module 7 to 90 or 120 seconds.

### "Module not found" when re-uploading
The full list of working module IDs is in [architecture.md](./architecture.md#module-ids-discovered-the-hard-way).
Common gotchas:
- Sleep is `util:FunctionSleep`, NOT `util:Sleep` or `builtin:BasicSleep`.
- Set Variables is `util:SetVariables`, NOT `util:SetVariables2`.

### Pulling / pushing scenario blueprint
```bash
# Pull current state (overwrites existing-blueprint.json)
curl -sS -H "Authorization: Token $MAKE_API_TOKEN" \
  "https://us2.make.com/api/v2/scenarios/5048310/blueprint" \
  -o existing-blueprint.json

# Push local blueprint.json (updates scenario in place)
bash upload.sh           # update scenario 5048310
bash upload.sh new       # create a new scenario instead
```

## File map

```
shopee-pipeline/
├── .env                    # all secrets (gitignored)
├── .gitignore
├── blueprint.json          # source-of-truth scenario definition
├── upload.sh               # injects .env keys, PATCHes Make API
├── existing-blueprint.json # last pulled state (for diffing/rollback)
├── scraper/
│   ├── scrape_shopee.py    # CSV / live-API → Inbox loader
│   ├── requirements.txt
│   ├── products.csv.example
│   └── service-account.json  # Google service account (gitignored, you must create)
├── docs/
│   ├── README.md           # ← you are here
│   └── architecture.md     # data flow, module IDs, costs, limits
└── .github/workflows/
    └── scrape.yml          # GitHub Actions daily scrape (optional)
```

## Roadmap (priority order)

1. **Upgrade JSON2Video to paid tier** (~$20/mo, 120min render = ~130 videos). Without this
   you're capped at 1 video/month. This is the single biggest blocker.
2. **Replace module 7 (single sleep) with a repeater + status check** so renders >60s don't fail.
3. **Switch ElevenLabs from "fire-and-forget" to "upload result to JSON2Video CDN"**, then
   pass the audio URL into the JSON2Video movie definition. Higher quality voice than
   the JSON2Video built-in TTS.
4. **TikTok auto-post**: either Publer Business ($15/mo) or audit your TikTok app for
   Content Posting API public-feed access (Business account required).
5. **Live Shopee scraper**: swap `requests` for `curl_cffi` with browser impersonation,
   add `--keyword` rotation, run on GitHub Actions cron daily.
6. **Performance feedback loop**: hourly poll of TikTok/Shopee analytics → Performance tab →
   weekly Claude review → "kill bad niches, double down on winners".
