"""FastAPI app: Plaid linking, transaction sync, and budget endpoints."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.affordability import check_purchase
from app.budget import budget_status
from app.categorize import categorize_transaction
from app.config import IS_SANDBOX, PLAID_ENV
from app.db import (
    TransactionRecord,
    get_access_token,
    get_budgets,
    get_db,
    get_transactions,
    init_db,
    save_item,
    set_budget,
    upsert_transactions,
)
from app.explain import explain_verdict
from app.plaid_client import create_link_token, exchange_public_token, fetch_transactions
from app.recommend import recommend_budgets

# Single-process, in-memory cooldown. Fine for the MVP's single-worker demo
# deployment; move to a shared store (Redis, or a DB-backed timestamp) before
# running multiple workers, since each process would otherwise track its own
# cooldown and the effective rate limit would multiply by worker count.
SYNC_COOLDOWN_SECONDS = 60
_last_sync_at: dict[str, datetime] = {}

# Shorter cooldown than /sync (no Plaid call here, just an LLM call) - mainly
# guards against a double-click firing two Claude requests for one check.
AFFORDABILITY_COOLDOWN_SECONDS = 5
_last_affordability_check_at: dict[str, datetime] = {}

# A heavier LLM call (whole spending history, multiple categories) than the
# affordability check, so a longer cooldown.
RECOMMEND_COOLDOWN_SECONDS = 15
_last_recommend_at: dict[str, datetime] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Expense Tracker", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class LinkTokenRequest(BaseModel):
    user_id: str


class LinkTokenResponse(BaseModel):
    link_token: str


class ExchangeRequest(BaseModel):
    user_id: str
    public_token: str


class ExchangeResponse(BaseModel):
    status: str


class SyncRequest(BaseModel):
    user_id: str


class SyncResponse(BaseModel):
    synced_count: int


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    transaction_id: str
    date: str
    name: str
    merchant_name: Optional[str]
    amount: float
    category: str


class SetBudgetRequest(BaseModel):
    user_id: str
    category: str
    amount: float


class BudgetOut(BaseModel):
    category: str
    amount: float


class ConfigOut(BaseModel):
    plaid_env: str
    is_sandbox: bool


class AffordabilityRequest(BaseModel):
    user_id: str
    price: float
    category: str
    timing: str


class AffordabilityResponse(BaseModel):
    verdict: str
    explanation: str
    explanation_source: str
    math: dict


class RecommendBudgetRequest(BaseModel):
    user_id: str
    months: int = 6


class CategoryRecommendationOut(BaseModel):
    category: str
    recommended_budget: float
    rationale: str


class RecommendBudgetResponse(BaseModel):
    recommendations: list[CategoryRecommendationOut]
    summary: str
    source: str


def _check_sync_rate_limit(user_id: str) -> None:
    now = datetime.now(timezone.utc)
    last = _last_sync_at.get(user_id)
    if last is not None:
        elapsed = (now - last).total_seconds()
        if elapsed < SYNC_COOLDOWN_SECONDS:
            retry_after = round(SYNC_COOLDOWN_SECONDS - elapsed)
            raise HTTPException(status_code=429, detail=f"Rate limited, retry after {retry_after}s")
    _last_sync_at[user_id] = now


def _check_affordability_rate_limit(user_id: str) -> None:
    now = datetime.now(timezone.utc)
    last = _last_affordability_check_at.get(user_id)
    if last is not None:
        elapsed = (now - last).total_seconds()
        if elapsed < AFFORDABILITY_COOLDOWN_SECONDS:
            retry_after = round(AFFORDABILITY_COOLDOWN_SECONDS - elapsed)
            raise HTTPException(status_code=429, detail=f"Rate limited, retry after {retry_after}s")
    _last_affordability_check_at[user_id] = now


def _check_recommend_rate_limit(user_id: str) -> None:
    now = datetime.now(timezone.utc)
    last = _last_recommend_at.get(user_id)
    if last is not None:
        elapsed = (now - last).total_seconds()
        if elapsed < RECOMMEND_COOLDOWN_SECONDS:
            retry_after = round(RECOMMEND_COOLDOWN_SECONDS - elapsed)
            raise HTTPException(status_code=429, detail=f"Rate limited, retry after {retry_after}s")
    _last_recommend_at[user_id] = now


def _current_month_range() -> tuple[str, str]:
    today = datetime.now(timezone.utc)
    return today.strftime("%Y-%m-01"), today.strftime("%Y-%m-%d")


def _current_status(db: Session, user_id: str) -> dict:
    start_date, end_date = _current_month_range()
    transactions = get_transactions(db, user_id, start_date=start_date, end_date=end_date)
    actual_spend = _sum_by_stored_category(transactions)
    budgets = get_budgets(db, user_id)
    return budget_status(budgets, actual_spend)


def _sum_by_stored_category(transactions: list[TransactionRecord]) -> dict[str, float]:
    spend: dict[str, float] = {}
    for t in transactions:
        spend[t.category] = spend.get(t.category, 0.0) + t.amount
    return {category: round(total, 2) for category, total in spend.items()}


def _transactions_as_dicts(transactions: list[TransactionRecord]) -> list[dict]:
    """Stored records already carry their category (computed once at sync
    time) - include it so budget.spending_trend reuses it instead of trying
    to re-derive one from raw Plaid fields these records don't have."""
    return [{"date": t.date, "amount": t.amount, "category": t.category} for t in transactions]


@app.get("/config", response_model=ConfigOut)
def get_config() -> ConfigOut:
    return ConfigOut(plaid_env=PLAID_ENV, is_sandbox=IS_SANDBOX)


@app.post("/link/token", response_model=LinkTokenResponse)
def link_token(payload: LinkTokenRequest) -> LinkTokenResponse:
    token = create_link_token(user_id=payload.user_id)
    return LinkTokenResponse(link_token=token)


@app.post("/link/exchange", response_model=ExchangeResponse)
def link_exchange(payload: ExchangeRequest, db: Session = Depends(get_db)) -> ExchangeResponse:
    access_token = exchange_public_token(payload.public_token)
    save_item(db, payload.user_id, access_token)
    return ExchangeResponse(status="ok")


@app.post("/sync", response_model=SyncResponse)
def sync(payload: SyncRequest, db: Session = Depends(get_db)) -> SyncResponse:
    _check_sync_rate_limit(payload.user_id)

    access_token = get_access_token(db, payload.user_id)
    if access_token is None:
        raise HTTPException(status_code=404, detail="No linked bank account for this user_id")

    raw_transactions = fetch_transactions(access_token)
    categorized = [
        {
            "transaction_id": txn["transaction_id"],
            "date": txn["date"],
            "name": txn["name"],
            "merchant_name": txn.get("merchant_name"),
            "amount": txn["amount"],
            "category": categorize_transaction(txn),
        }
        for txn in raw_transactions
    ]
    count = upsert_transactions(db, payload.user_id, categorized)
    return SyncResponse(synced_count=count)


@app.get("/transactions", response_model=list[TransactionOut])
def list_transactions(
    user_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
) -> list[TransactionRecord]:
    return get_transactions(db, user_id, start_date=start_date, end_date=end_date, category=category)


@app.get("/budget/status")
def get_budget_status(
    user_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
) -> dict:
    if start_date is None or end_date is None:
        default_start, default_end = _current_month_range()
        start_date = start_date or default_start
        end_date = end_date or default_end

    transactions = get_transactions(db, user_id, start_date=start_date, end_date=end_date)
    actual_spend = _sum_by_stored_category(transactions)
    budgets = get_budgets(db, user_id)
    return budget_status(budgets, actual_spend)


@app.post("/budget", response_model=BudgetOut)
def create_or_update_budget(payload: SetBudgetRequest, db: Session = Depends(get_db)) -> BudgetOut:
    record = set_budget(db, payload.user_id, payload.category, payload.amount)
    return BudgetOut(category=record.category, amount=record.amount)


@app.post("/affordability/check", response_model=AffordabilityResponse)
def check_affordability(payload: AffordabilityRequest, db: Session = Depends(get_db)) -> AffordabilityResponse:
    _check_affordability_rate_limit(payload.user_id)

    if payload.price <= 0:
        raise HTTPException(status_code=400, detail="price must be positive")

    status = _current_status(db, payload.user_id)
    try:
        math = check_purchase(status, payload.price, payload.category, payload.timing)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    explained = explain_verdict(math)
    return AffordabilityResponse(
        verdict=math["verdict"],
        explanation=explained["explanation"],
        explanation_source=explained["source"],
        math=math,
    )


@app.post("/budget/recommend", response_model=RecommendBudgetResponse)
def recommend_budget(payload: RecommendBudgetRequest, db: Session = Depends(get_db)) -> RecommendBudgetResponse:
    _check_recommend_rate_limit(payload.user_id)

    transactions = get_transactions(db, payload.user_id)
    budgets = get_budgets(db, payload.user_id)
    result = recommend_budgets(_transactions_as_dicts(transactions), budgets, months=payload.months)
    return RecommendBudgetResponse(
        recommendations=result["recommendations"],
        summary=result["summary"],
        source=result["source"],
    )
