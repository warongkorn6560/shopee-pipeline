# Pipeline architecture

## Data flow

```
                  ┌────────────────────────────────────────────────────────────┐
                  │  Google Sheet: "Shopee Affiliate Pipeline"                 │
                  │  ID 1nuxfK86v0X8rP0q58fyqm2gwF4bedOoyMSH6iOwu0aY           │
                  │                                                            │
                  │  Tabs: Inbox | Production | Performance                    │
                  └─────▲──────────────────────────────────────────────────────┘
                        │ append
                        │
   ┌────────────────────┴───────────────────┐
   │ Python scraper (scraper/scrape_shopee) │
   │  source: CSV (V1) or live API (V2)     │
   │  schedule: cron / GitHub Actions       │
   └────────────────────────────────────────┘
                        │
                        ▼
   ┌────────────────────────────────────────────────────────────────────────────┐
   │  Make.com scenario 5048310 — "Shopee Affiliate Video Pipeline"             │
   │                                                                            │
   │  [1] google-sheets:watchRows           (Inbox tab, polls every 15min)      │
   │   │                                                                        │
   │  [2] anthropic-claude:simpleTextPrompt (Haiku 4.5 -> JSON script bundle)   │
   │   │                                                                        │
   │  [3] util:SetVariables                 (parseJSON ONCE -> named vars)      │
   │   │                                                                        │
   │  [4] http:ActionSendData               (ElevenLabs TTS, voice Charlotte)   │
   │   │                                                                        │
   │  [5] google-sheets:addRow              (append to Production tab)          │
   │   │                                                                        │
   │  [6] http:ActionSendData               (POST JSON2Video create movie)      │
   │   │                                                                        │
   │  [7] util:FunctionSleep                (60s wait for render)               │
   │   │                                                                        │
   │  [8] http:ActionSendData               (GET JSON2Video movie status)       │
   │   │                                                                        │
   │  [9] http:ActionSendData               (Telegram sendMessage to user)      │
   └────────────────────────────────────────────────────────────────────────────┘
                        │
                        ▼
              ┌──────────────────────────────────────┐
              │  Telegram chat 1165507312            │
              │  Bot @warong_shopee_bot              │
              │  Receives: MP4 URL, caption,         │
              │  hashtags, affiliate URL, alt hooks  │
              └──────────────────────────────────────┘
                        │ (manual)
                        ▼
              Open Shopee/TikTok/IG apps -> upload MP4 -> paste caption.
```

## The `Set Variables` pattern (why this matters)

Past attempts inlined `{{parseJSON(2.result).script}}` into every downstream module,
which produced nested `{{}}` bracket syntax errors. Module 3 (`util:SetVariables`)
parses Claude's JSON ONCE into clean named variables (`script`, `caption`, `hashtags`,
`hook_alt_1`, `hook_alt_2`, `product_name`, `product_price`, `affiliate_url`).
Every downstream module references those as `{{3.script}}` etc. — single-level only.

## Module IDs (discovered the hard way)

| What you see in the UI       | Module ID in blueprint JSON              |
|------------------------------|------------------------------------------|
| Google Sheets — Watch Rows   | `google-sheets:watchRows` v2             |
| Google Sheets — Add a Row    | `google-sheets:addRow` v2                |
| Anthropic Claude — Prompt    | `anthropic-claude:simpleTextPrompt` v1   |
| Tools — Set multiple vars    | `util:SetVariables` v1                   |
| Tools — Sleep                | `util:FunctionSleep` v1                  |
| HTTP — Make a request        | `http:ActionSendData` v3                 |

Save these somewhere — `builtin:BasicSleep`, `util:Sleep`, `tools:Sleep` all return
`Module not found` from the Make API.

## Why HTTP modules instead of native ElevenLabs / JSON2Video / Telegram apps

- Make's SDK apps endpoint (`/api/v2/sdk/apps/<name>/modules`) only exposes custom
  apps. Native marketplace apps don't list their module IDs anywhere queryable.
- The user has connections set up for all three apps (IDs 8854953, 8855638, 8856506),
  but using them requires knowing the exact `{vendor}:{moduleName}@{version}` triple.
- `http:ActionSendData` is universal, well-documented, and renders the same outputs.

If you later want to migrate to the native modules, add them via the Make UI, then
re-run `bash upload.sh` from the GUI-saved blueprint (Make UI -> Scenario -> ⋯ -> Export).

## API costs / limits

| Service     | Tier        | Limit                         | Approx cost per video |
|-------------|-------------|-------------------------------|-----------------------|
| Make.com    | Free        | 1,000 ops/mo                  | ~9 ops/video → ~110 vids/mo |
| Anthropic   | Make built-in or BYO | varies                | ~1,200 tokens out → ~$0.001 |
| ElevenLabs  | Free        | 10,000 chars/mo               | ~600 chars → ~16 vids/mo (free) |
| JSON2Video  | Free        | 60 sec render time/mo         | ~55 sec/video → 1 video/mo (free!) |
| Telegram    | Free        | unlimited                     | $0 |

**Free-tier JSON2Video allows only ~1 full video per month.** Upgrade to the
$20/mo plan for ~120 minutes (~130 videos). This is the binding constraint.

## What's NOT in the pipeline

1. **Shopee Video upload** — no public API. Manual via the Shopee app, ~30s/video.
2. **TikTok auto-post to public feed** — unaudited apps post to drafts only.
   Either (a) accept drafts and publish manually, (b) upgrade TikTok account to
   Business and use TikTok Content Posting API with audit, or (c) use Publer
   Business ($15/mo) which has video-upload support.
3. **JSON2Video render polling beyond 60s** — V1 does a single poll. If your
   videos sometimes take longer, replace module 7+8 with a Make `repeater` or
   use JSON2Video's webhook callback into a second scenario.
4. **Image/video stock selection** — currently hardcoded Pexels URL in the
   blueprint. Future: have Claude return a stock keyword and pass to Pexels API.
