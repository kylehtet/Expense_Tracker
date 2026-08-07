# can_u_afford_it

A free, open expense tracker (Plaid-powered) with a built-in "Can I afford this?" checker.

Educational estimate only, not financial advice.

## Stack

- Backend: Python (FastAPI)
- Frontend: React + Tailwind
- Bank data: Plaid API (Sandbox by default — see `PLAID_ENV` in `backend/.env.example`)
- Affordability checker: deterministic rules engine (`backend/app/rules.py`) + a local Chroma RAG layer (`backend/app/retrieval.py`) for mortgage rates, property tax/insurance, and cost-of-living facts, with sources and freshness shown for every number
- LLM: Claude API (Haiku 4.5 for query parsing, Sonnet 5 for plain-language explanations)

## Backend setup

```
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in ANTHROPIC_API_KEY, PLAID_CLIENT_ID, PLAID_SECRET
pytest
```
