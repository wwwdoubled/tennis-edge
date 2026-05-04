# Tennis Edge

> Surface-aware Elo ratings, match predictions and (eventually) value bets for ATP & WTA tennis.

This is **phase 1 — the foundation**: data pipeline, sELO ratings, an API, and a minimal editorial dashboard. Phase 2 adds the ML model. Phase 3 adds the parlay ("raspadinha") builder. Phase 4 adds odds ingestion and edge detection.

---

## What's in this repo

```
.
├── app/                  Next.js 15 app (the dashboard)
├── components/           React components
├── api/                  FastAPI serverless functions (Vercel Python runtime)
│   ├── index.py          Routes: /health /players /rankings /predict
│   └── _lib/             Shared Python: elo, db, sackmann, repo
├── scripts/              Pipeline jobs (run via GitHub Actions)
│   ├── init_db.py        Apply schema
│   ├── seed_history.py   One-time historical load (2005 → today)
│   └── update_data.py    Daily incremental update
├── db/schema.sql         Postgres schema
├── .github/workflows/    CI: seed-history (manual) + update-data (daily cron)
├── vercel.json           Routes /api/* to FastAPI
├── requirements.txt      Python deps for scripts
└── api/requirements.txt  Python deps for serverless functions
```

---

## How it deploys

```
GitHub repo
  ├──► GitHub Actions (cron) ──► writes to Neon Postgres
  └──► Vercel (auto-deploy on push)
         ├── Next.js dashboard
         └── /api/* → FastAPI serverless functions ──► reads from Neon
```

You don't run a server. Everything is serverless or scheduled.

---

## Setup — first time

### 1. Create a Postgres database on [Neon](https://neon.tech)
Free tier is fine. Copy the **pooled** connection string (it has `-pooler` in the host).

### 2. Push this repo to GitHub
```bash
git init
git add .
git commit -m "initial: tennis edge foundation"
git remote add origin git@github.com:YOU/tennis-edge.git
git push -u origin main
```

### 3. Add the secret to GitHub
GitHub repo → Settings → Secrets and variables → Actions → **New repository secret**
- Name: `DATABASE_URL`
- Value: your Neon pooled connection string

### 4. Run the seed workflow (one time)
GitHub repo → Actions → **Seed historical data** → Run workflow
- start_year: `2005` (sensible default — gives ~150k matches)
- tour: `BOTH`

This takes 5–15 min and populates ~150k matches with surface-aware Elo.

### 5. Connect Vercel
- Import the repo on [vercel.com](https://vercel.com)
- Set the env var `DATABASE_URL` (same value as in GitHub)
- Vercel auto-detects Next.js and the Python `/api` folder
- Deploy

The dashboard will be live at `https://your-project.vercel.app`.

### 6. The daily cron just works
The `update-data.yml` workflow runs at 06:00 UTC daily and pulls any new matches from Sackmann's repo.

---

## Local dev

```bash
# Python
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r api/requirements.txt

# Apply schema + seed (warning: takes a while)
cp .env.example .env       # fill in DATABASE_URL
export $(cat .env | xargs)
python -m scripts.init_db
python -m scripts.seed_history --start 2020 --tour ATP   # smaller set for testing

# Frontend
npm install
npm run dev
```

The Vercel dev server runs both the Next.js app and the FastAPI functions if you use `vercel dev`. Without that, you can still hit the FastAPI functions directly with `uvicorn api.index:app --reload --port 8000` and proxy from Next.js.

---

## Phase 2 onwards (not yet built)

- **ML model** (XGBoost) using sELO + form + fatigue + H2H as features
- **Point-by-point simulator** for derived markets (set betting, total games, etc.)
- **Odds ingestion** from The Odds API + devigging (Shin's method)
- **Edge detection**: only flag bets where `model_p × market_odds > 1 + buffer`
- **Parlay builder** with correlation-adjusted combo odds
- **CLV tracking** — the only honest metric of long-term skill

Each of these gets a feature branch and a separate UI page.

---

## A note on realism

Bookmaker margins on tennis are ~5–7%. Beating that consistently is hard. **Always backtest before risking money.** A model that hits 53% on tossups isn't beating the market — it's gambling at a slightly less unfair rate. The metric that matters is **closing line value**. If you don't beat the closing line, you don't have edge, period.
