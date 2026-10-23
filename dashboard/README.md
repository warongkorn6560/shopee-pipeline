# Pipeline Control

Password-protected dashboard for both video flows in this repo:

- **Flow A — Shopee Affiliate** (`.github/workflows/daily-video.yml`, `scrape.yml`)
- **Flow B — เรื่องเล่าจากแผนที่** (`.github/workflows/story-video.yml`)

It runs workflows, pauses/resumes their schedules, edits the GitHub Actions
variables the pipeline reads, manages the Google Sheet queues, and shows live
quotas plus a billing summary.

Production: https://pipeline-dashboard-seven-kappa.vercel.app (Vercel project `pipeline-dashboard`).

## Environment variables (Vercel → Settings → Environment Variables)

| Name | Needed for |
|---|---|
| `DASHBOARD_PASSWORD`, `SESSION_SECRET` (32+ chars) | sign-in |
| `GITHUB_TOKEN` | run / schedule / settings — fine-grained PAT on this repo only: Actions RW, Variables RW, Secrets RW (to save the Claude key), Contents R |
| `GOOGLE_SHEET_ID`, `GOOGLE_SERVICE_ACCOUNT_JSON` (full JSON) | queues |
| `ELEVENLABS_API_KEY`, `AI_GATEWAY_API_KEY`, `TELEGRAM_BOT_TOKEN` | live health gauges |

## Local development

```bash
npm install
npm run dev
```

Put the same variables in `dashboard/.env.local` (git-ignored).

Deploys are automatic: the Vercel project tracks `main` with root directory
`dashboard`, and `vercel.json` skips builds when a push doesn't touch this folder.
Environment variable changes need a redeploy (Vercel → Deployments → Redeploy).
