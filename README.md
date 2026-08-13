# Expense Tracker

A free, open personal finance app powered by Plaid. Connect a bank account and it sorts
transactions into six fixed categories, tracks them against budgets you set, and — the actual
point of the app — tells you whether you can afford something *before* you spend, not after.
Savings goals and recurring-charge detection build on the same real, synced data.

Educational estimate only, not financial advice, and not a licensed financial service.

## Features

- **Bank sync** — Plaid Link (Sandbox or Production), read-only, encrypted access token
- **Six fixed categories** — Housing, Food, Transport, Subscriptions, Entertainment, Other
- **Budgets** — a monthly limit per category, with AI-recommended starting points from real spending history
- **"Can I afford this?"** — a deterministic rules engine checks a purchase against real budget headroom; an LLM only writes the plain-language explanation afterward, never the math
- **Savings goals** — track progress toward a target, with a pace check that flags when spending is putting a goal behind schedule, plus an auto-budget suggestion to get back on track
- **Recurring charges** — detects subscriptions/recurring merchants from transaction history
- **Firebase Authentication** — email/password, ID-token based, no separate password stored by this app

## Stack

- Backend: Python (FastAPI + SQLAlchemy + SQLite)
- Frontend: React 19 + Vite + Tailwind v4
- Auth: Firebase Authentication (frontend SDK) + `firebase-admin` (backend token verification)
- Bank data: Plaid API (Sandbox by default — see `PLAID_ENV` in `backend/.env.example`)
- Affordability facts: deterministic rules engine (`backend/app/rules.py`, `app/affordability.py`) + a local Chroma RAG layer (`backend/app/retrieval.py`) for mortgage rates, property tax/insurance, and cost-of-living facts, with sources and freshness shown for every number
- LLM: Claude API — used only for plain-language explanations, budget recommendations, and auto-budget suggestions, always on top of numbers computed deterministically first

## Local setup

### Backend

```
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# fill in ANTHROPIC_API_KEY, PLAID_CLIENT_ID, PLAID_SECRET, ENCRYPTION_KEY,
# and either FIREBASE_SERVICE_ACCOUNT_PATH or FIREBASE_SERVICE_ACCOUNT_JSON
pytest
uvicorn app.main:app --reload --port 8000
```

`ENCRYPTION_KEY` (encrypts the Plaid access token at rest):
```
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

`FIREBASE_SERVICE_ACCOUNT_PATH` / `FIREBASE_SERVICE_ACCOUNT_JSON`: a service account key from
Firebase Console → Project Settings → Service Accounts → Generate New Private Key. Never commit
this file — use the `_JSON` env var instead on hosts with no writable filesystem to drop it on.

### Frontend

```
cd frontend
npm install
cp .env.example .env
# fill in VITE_FIREBASE_API_KEY, VITE_FIREBASE_AUTH_DOMAIN, VITE_FIREBASE_PROJECT_ID,
# VITE_FIREBASE_APP_ID (from Firebase Console -> Project Settings -> Your apps -> Web app)
npm run dev   # http://localhost:5173
```

Both need to be running at once for the app to work end to end.

## Deployment

`render.yaml` at the repo root is a Render Blueprint defining both services (FastAPI backend on
a persistent disk so linked-bank data survives redeploys, plus the static frontend build). Push
to GitHub, connect the repo on Render, and it picks up both services from that file — you'll
still need to fill in the real secrets (Plaid keys, encryption key, Anthropic key, Firebase
service account JSON, Firebase web config) in Render's dashboard yourself, and add the deployed
frontend domain to Firebase Console → Authentication → Settings → Authorized domains.

Persistent disks on Render require a paid plan, not the free tier.

## Data & privacy

The Plaid access token is encrypted at rest and never sent back to the browser or logged.
Transactions and budgets are stored in this app's own database, scoped per user. No analytics,
tracking, or third-party scripts beyond Plaid itself.
