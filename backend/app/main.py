"""FastAPI app: Plaid linking, transaction sync, and budget endpoints."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, EmailStr
from sqlalchemy.orm import Session as DbSession

from app.affordability import check_purchase
from app.budget import budget_status
from app.categorize import INTERNAL_CATEGORIES, categorize_transaction
from app.config import ALLOWED_ORIGINS, IS_SANDBOX, PLAID_ENV
from app.db import (
    GoalRecord,
    TransactionRecord,
    abandon_goal,
    add_interest_signup,
    count_production_links,
    create_goal,
    delete_item,
    delete_transactions_by_ids,
    delete_transactions_for_user,
    get_access_token,
    get_budgets,
    get_db,
    get_goal,
    get_goals,
    get_transactions,
    init_db,
    record_production_link,
    save_item,
    set_budget,
    set_transaction_category,
    update_goal,
    upsert_transactions,
)
from app.auto_budget import recommend_budget_for_goal
from app.explain import explain_verdict
from app.firebase_auth import init_firebase_app, require_firebase_auth
from app.goal_tracker import (
    check_goal_health,
    compute_monthly_savings_capacity,
    plan_from_affordability_check,
    redirect_impact,
    required_additional_capacity,
)
from app.income import estimate_annual_income
from app.plaid_client import create_link_token, exchange_public_token, fetch_transactions, remove_item
from app.recommend import recommend_budgets, spending_profile
from app.recurring import detect_recurring_charges
from app.retrieval import fetch_mortgage_rates, load_property_tax_insurance, retrieve_housing_context
from app.rules import housing_affordability

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

# Same shape as RECOMMEND_COOLDOWN_SECONDS above - this was the one LLM
# endpoint with no cooldown at all (a GET, no less), so it had no guard
# against a user just refreshing the page repeatedly to re-trigger paid
# Claude calls.
AUTO_BUDGET_COOLDOWN_SECONDS = 15
_last_auto_budget_at: dict[str, datetime] = {}

# Plaid Trial plan cap as of this app's setup (2026-08) - see
# app.db.ProductionLinkEvent for why this is a lifetime count, not a
# currently-connected count.
PRODUCTION_CONNECTION_LIMIT = 10

# Shared, pre-seeded account anyone can log into from the landing page to try
# the real app without connecting a real (or even a Sandbox) bank themselves.
# Read-only by convention, not by database permissions - every endpoint that
# would change this account's data rejects it explicitly instead.
DEMO_UID = "k5lRfPrAXuhTKU2VNkaZINIAhx92"


def _reject_if_demo(uid: str) -> None:
    if uid == DEMO_UID:
        raise HTTPException(
            status_code=403, detail="This is the shared demo account - changes here aren't saved."
        )

# Unauthenticated (no Firebase login) - keyed by request IP rather than uid,
# since there's no account to key on yet. Generous cooldown, just enough to
# blunt a scripted spam loop; the email-format check and unique-email dedupe
# in app.db do most of the real work.
INTEREST_SIGNUP_COOLDOWN_SECONDS = 30
_last_interest_signup_at: dict[str, datetime] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_firebase_app()
    yield


app = FastAPI(title="Expense Tracker", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LinkTokenResponse(BaseModel):
    link_token: str


class ExchangeRequest(BaseModel):
    public_token: str


class ExchangeResponse(BaseModel):
    status: str


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
    category: str
    amount: float


class BudgetOut(BaseModel):
    category: str
    amount: float


class ConfigOut(BaseModel):
    plaid_env: str
    is_sandbox: bool
    production_connections_used: int = 0
    production_connections_limit: int = PRODUCTION_CONNECTION_LIMIT


class DisconnectResponse(BaseModel):
    status: str


class AffordabilityRequest(BaseModel):
    price: float
    category: str
    timing: str
    location: Optional[str] = None


class RetrievedFactOut(BaseModel):
    text: str
    category: str
    source: str
    stale: bool


class AffordabilityResponse(BaseModel):
    verdict: str
    explanation: str
    explanation_source: str
    math: dict
    retrieved_facts: list[RetrievedFactOut] = []
    savings_plan: Optional[SavingsPlanOut] = None


class HomeAffordabilityRequest(BaseModel):
    price: float
    down_payment: float
    loan_term_months: int = 360
    interest_rate: Optional[float] = None  # annual decimal; defaults to current RAG-sourced rate
    property_tax_rate: Optional[float] = None  # annual decimal; defaults to RAG-sourced state rate
    annual_insurance_estimate: Optional[float] = None  # defaults to RAG-sourced state average
    other_monthly_debts: float = 0.0  # sum of recurring charges the user marked as debt obligations
    location: Optional[str] = None


class IncomeSourceOut(BaseModel):
    source: str
    average_amount: float
    average_interval_days: int
    occurrences: int
    last_received: str
    periods_per_year: int
    estimated_annual: float


class HomeAffordabilityResponse(BaseModel):
    affordable: bool
    max_affordable_price: float
    monthly_payment_estimate: float
    monthly_principal_interest: float
    monthly_property_tax: float
    monthly_insurance: float
    monthly_income: float
    front_end_ratio: float
    dti_ratio: float
    front_end_limit: float
    back_end_limit: float
    estimated_annual_income: float
    income_sources: list[IncomeSourceOut]
    other_monthly_debts: float
    interest_rate_used: float
    property_tax_rate_used: float
    annual_insurance_estimate_used: float
    retrieved_facts: list[RetrievedFactOut] = []


class RecommendBudgetRequest(BaseModel):
    months: int = 6
    target_total: Optional[float] = None


class CategoryRecommendationOut(BaseModel):
    category: str
    recommended_budget: float
    rationale: str


class RecommendBudgetResponse(BaseModel):
    recommendations: list[CategoryRecommendationOut]
    summary: str
    source: str


class MeResponse(BaseModel):
    uid: str
    has_linked_bank: bool


class SavingsPlanOut(BaseModel):
    gap: float
    monthly_savings_capacity: float
    months_to_goal: Optional[float]


class CreateGoalRequest(BaseModel):
    name: str
    target_amount: float
    category: str
    target_date: Optional[str] = None
    current_saved: float = 0.0


class UpdateGoalRequest(BaseModel):
    name: Optional[str] = None
    target_amount: Optional[float] = None
    target_date: Optional[str] = None
    current_saved: Optional[float] = None


class GoalHealthOut(BaseModel):
    on_track: bool
    pace_status: str
    projected_shortfall: float
    projected_completion_date: Optional[str]
    reason: str


class GoalOut(BaseModel):
    id: int
    name: str
    target_amount: float
    target_date: Optional[str]
    current_saved: float
    category: str
    monthly_savings_capacity: float
    status: str
    health: GoalHealthOut


class GoalActionResponse(BaseModel):
    status: str


class CategoryBudgetSuggestionOut(BaseModel):
    category: str
    suggested_budget: float
    rationale: str


class AutoBudgetOut(BaseModel):
    required_cut: float
    suggestions: list[CategoryBudgetSuggestionOut]
    summary: str
    source: str


class RecurringGoalImpactOut(BaseModel):
    goal_id: int
    goal_name: str
    months_sooner: Optional[float]
    newly_reachable: bool
    hypothetical_months_to_goal: Optional[float]


class RecurringChargeOut(BaseModel):
    merchant: str
    average_amount: float
    category: str
    occurrences: int
    first_seen: str
    last_charged: str
    next_charge_estimate: str
    verdict: str
    impact_on_goals: Optional[list[RecurringGoalImpactOut]] = None


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


def _check_auto_budget_rate_limit(user_id: str) -> None:
    now = datetime.now(timezone.utc)
    last = _last_auto_budget_at.get(user_id)
    if last is not None:
        elapsed = (now - last).total_seconds()
        if elapsed < AUTO_BUDGET_COOLDOWN_SECONDS:
            retry_after = round(AUTO_BUDGET_COOLDOWN_SECONDS - elapsed)
            raise HTTPException(status_code=429, detail=f"Rate limited, retry after {retry_after}s")
    _last_auto_budget_at[user_id] = now


def _current_month_range() -> tuple[str, str]:
    today = datetime.now(timezone.utc)
    return today.strftime("%Y-%m-01"), today.strftime("%Y-%m-%d")


def _current_status(db: DbSession, user_id: str) -> dict:
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


def _housing_context(location: Optional[str]) -> list[dict]:
    """RAG facts for a Housing affordability check. Retrieval is best-effort -
    a Chroma/network hiccup here shouldn't break the deterministic verdict,
    just mean the explanation goes out without external facts woven in."""
    try:
        return retrieve_housing_context(location or "")
    except Exception:
        return []


def _infer_state(location: Optional[str], states: list[dict]) -> Optional[dict]:
    """Best-effort match of a free-text location against the property-tax/
    insurance dataset's state list, by 2-letter code or full name appearing
    anywhere in the string. Returns None (caller falls back to a national
    average) rather than guessing wrong."""
    if not location:
        return None
    tokens = location.lower().replace(",", " ").split()
    for state in states:
        if state["state"].lower() in tokens or state["state_name"].lower() in location.lower():
            return state
    return None


def _transactions_as_dicts(transactions: list[TransactionRecord]) -> list[dict]:
    """Stored records already carry their category (computed once at sync
    time) - include it so budget.spending_trend reuses it instead of trying
    to re-derive one from raw Plaid fields these records don't have."""
    return [{"date": t.date, "amount": t.amount, "category": t.category} for t in transactions]


def _goal_as_dict(goal: GoalRecord) -> dict:
    return {
        "target_amount": goal.target_amount,
        "current_saved": goal.current_saved,
        "monthly_savings_capacity": goal.monthly_savings_capacity,
        "category": goal.category,
        "target_date": goal.target_date,
    }


def _goal_out(goal: GoalRecord, budgets: dict, transactions: list[dict]) -> GoalOut:
    health = check_goal_health(_goal_as_dict(goal), budgets, transactions)
    return GoalOut(
        id=goal.id,
        name=goal.name,
        target_amount=goal.target_amount,
        target_date=goal.target_date,
        current_saved=goal.current_saved,
        category=goal.category,
        monthly_savings_capacity=goal.monthly_savings_capacity,
        status=goal.status,
        health=GoalHealthOut(**health),
    )


def _budgets_and_transactions(db: DbSession, user_id: str) -> tuple[dict, list[dict]]:
    budgets = get_budgets(db, user_id)
    transactions = _transactions_as_dicts(get_transactions(db, user_id))
    return budgets, transactions


def _transactions_for_recurring(transactions: list[TransactionRecord]) -> list[dict]:
    """Unlike _transactions_as_dicts, recurring-charge detection groups by
    merchant, so it needs the name/merchant_name fields that function
    deliberately leaves out."""
    return [
        {"date": t.date, "amount": t.amount, "category": t.category, "name": t.name, "merchant_name": t.merchant_name}
        for t in transactions
    ]


@app.get("/config", response_model=ConfigOut)
def get_config(db: DbSession = Depends(get_db)) -> ConfigOut:
    return ConfigOut(
        plaid_env=PLAID_ENV,
        is_sandbox=IS_SANDBOX,
        production_connections_used=count_production_links(db),
    )


class InterestSignupRequest(BaseModel):
    email: EmailStr


class InterestSignupResponse(BaseModel):
    status: str


@app.post("/interest", response_model=InterestSignupResponse)
def submit_interest(
    payload: InterestSignupRequest, request: Request, db: DbSession = Depends(get_db)
) -> InterestSignupResponse:
    client_ip = request.client.host if request.client else "unknown"
    now = datetime.now(timezone.utc)
    last = _last_interest_signup_at.get(client_ip)
    if last is not None and (now - last).total_seconds() < INTEREST_SIGNUP_COOLDOWN_SECONDS:
        raise HTTPException(status_code=429, detail="Too many requests - try again shortly")
    _last_interest_signup_at[client_ip] = now

    add_interest_signup(db, payload.email.lower())
    return InterestSignupResponse(status="ok")


@app.get("/auth/me", response_model=MeResponse)
def get_me(decoded_token: dict = Depends(require_firebase_auth), db: DbSession = Depends(get_db)) -> MeResponse:
    """Called by the frontend right after Firebase confirms an authenticated
    user, to learn whether that (real, server-verified) uid already has a
    linked bank - real backend state, not a per-browser guess, so it's
    correct even after logging in from a different device."""
    uid = decoded_token["uid"]
    return MeResponse(uid=uid, has_linked_bank=get_access_token(db, uid) is not None)


@app.post("/link/token", response_model=LinkTokenResponse)
def link_token(decoded_token: dict = Depends(require_firebase_auth)) -> LinkTokenResponse:
    _reject_if_demo(decoded_token["uid"])
    token = create_link_token(user_id=decoded_token["uid"])
    return LinkTokenResponse(link_token=token)


@app.post("/link/exchange", response_model=ExchangeResponse)
def link_exchange(
    payload: ExchangeRequest,
    decoded_token: dict = Depends(require_firebase_auth),
    db: DbSession = Depends(get_db),
) -> ExchangeResponse:
    uid = decoded_token["uid"]
    _reject_if_demo(uid)
    access_token = exchange_public_token(payload.public_token)
    save_item(db, uid, access_token)
    if not IS_SANDBOX:
        record_production_link(db, uid)
    return ExchangeResponse(status="ok")


@app.post("/link/disconnect", response_model=DisconnectResponse)
def disconnect(
    decoded_token: dict = Depends(require_firebase_auth), db: DbSession = Depends(get_db)
) -> DisconnectResponse:
    uid = decoded_token["uid"]
    _reject_if_demo(uid)
    access_token = delete_item(db, uid)
    if access_token is None:
        raise HTTPException(status_code=404, detail="No linked bank account for this user")
    try:
        remove_item(access_token)
    except Exception:
        # Item already gone/expired on Plaid's side, or a transient API error -
        # the local record is removed either way so the user can relink.
        pass
    delete_transactions_for_user(db, uid)
    return DisconnectResponse(status="ok")


@app.post("/sync", response_model=SyncResponse)
def sync(decoded_token: dict = Depends(require_firebase_auth), db: DbSession = Depends(get_db)) -> SyncResponse:
    uid = decoded_token["uid"]
    _reject_if_demo(uid)
    _check_sync_rate_limit(uid)

    access_token = get_access_token(db, uid)
    if access_token is None:
        raise HTTPException(status_code=404, detail="No linked bank account for this user")

    changes = fetch_transactions(access_token)
    categorized = [
        {
            "transaction_id": txn["transaction_id"],
            "date": txn["date"],
            "name": txn["name"],
            "merchant_name": txn.get("merchant_name"),
            "amount": txn["amount"],
            "category": categorize_transaction(txn),
        }
        for txn in changes["added"] + changes["modified"]
    ]
    count = upsert_transactions(db, uid, categorized)
    delete_transactions_by_ids(db, uid, changes["removed"])
    return SyncResponse(synced_count=count)


@app.get("/transactions", response_model=list[TransactionOut])
def list_transactions(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category: Optional[str] = None,
    decoded_token: dict = Depends(require_firebase_auth),
    db: DbSession = Depends(get_db),
) -> list[TransactionRecord]:
    return get_transactions(db, decoded_token["uid"], start_date=start_date, end_date=end_date, category=category)


class UpdateTransactionCategoryRequest(BaseModel):
    category: str


@app.patch("/transactions/{transaction_id}", response_model=TransactionOut)
def update_transaction_category(
    transaction_id: str,
    payload: UpdateTransactionCategoryRequest,
    decoded_token: dict = Depends(require_firebase_auth),
    db: DbSession = Depends(get_db),
) -> TransactionRecord:
    _reject_if_demo(decoded_token["uid"])
    if payload.category not in INTERNAL_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"category must be one of {INTERNAL_CATEGORIES}")
    txn = set_transaction_category(db, decoded_token["uid"], transaction_id, payload.category)
    if txn is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return txn


@app.get("/budget/status")
def get_budget_status(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    decoded_token: dict = Depends(require_firebase_auth),
    db: DbSession = Depends(get_db),
) -> dict:
    if start_date is None or end_date is None:
        default_start, default_end = _current_month_range()
        start_date = start_date or default_start
        end_date = end_date or default_end

    uid = decoded_token["uid"]
    transactions = get_transactions(db, uid, start_date=start_date, end_date=end_date)
    actual_spend = _sum_by_stored_category(transactions)
    budgets = get_budgets(db, uid)
    return budget_status(budgets, actual_spend)


@app.post("/budget", response_model=BudgetOut)
def create_or_update_budget(
    payload: SetBudgetRequest,
    decoded_token: dict = Depends(require_firebase_auth),
    db: DbSession = Depends(get_db),
) -> BudgetOut:
    _reject_if_demo(decoded_token["uid"])
    record = set_budget(db, decoded_token["uid"], payload.category, payload.amount)
    return BudgetOut(category=record.category, amount=record.amount)


@app.post("/affordability/check", response_model=AffordabilityResponse)
def check_affordability(
    payload: AffordabilityRequest,
    decoded_token: dict = Depends(require_firebase_auth),
    db: DbSession = Depends(get_db),
) -> AffordabilityResponse:
    uid = decoded_token["uid"]
    _check_affordability_rate_limit(uid)

    if payload.price <= 0:
        raise HTTPException(status_code=400, detail="price must be positive")

    status = _current_status(db, uid)
    try:
        math = check_purchase(status, payload.price, payload.category, payload.timing)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    retrieved_facts = _housing_context(payload.location) if payload.category == "Housing" else []
    explained = explain_verdict(math, retrieved_facts=retrieved_facts or None)

    savings_plan = None
    if math["verdict"] != "comfortable":
        budgets, all_transactions = _budgets_and_transactions(db, uid)
        plan = plan_from_affordability_check(payload.price, budgets, all_transactions)
        savings_plan = SavingsPlanOut(**plan)

    return AffordabilityResponse(
        verdict=math["verdict"],
        explanation=explained["explanation"],
        explanation_source=explained["source"],
        math=math,
        retrieved_facts=retrieved_facts,
        savings_plan=savings_plan,
    )


@app.post("/affordability/home-purchase", response_model=HomeAffordabilityResponse)
def check_home_affordability(
    payload: HomeAffordabilityRequest,
    decoded_token: dict = Depends(require_firebase_auth),
    db: DbSession = Depends(get_db),
) -> HomeAffordabilityResponse:
    """28/36 debt-to-income affordability check (app.rules.housing_affordability)
    fed by real data instead of manual entry: income and other-debt figures come
    from detecting the user's actual recurring deposits/charges, and the mortgage
    rate/property-tax/insurance defaults come from the RAG layer (app.retrieval)
    when not explicitly overridden. Only price, down payment, and loan term
    describe the hypothetical purchase itself - those can't come from past
    transaction history since they're about a home the user doesn't own yet."""
    uid = decoded_token["uid"]
    _check_affordability_rate_limit(uid)

    if payload.price <= 0:
        raise HTTPException(status_code=400, detail="price must be positive")
    if payload.down_payment < 0 or payload.down_payment > payload.price:
        raise HTTPException(status_code=400, detail="down_payment must be between 0 and price")
    if payload.other_monthly_debts < 0:
        raise HTTPException(status_code=400, detail="other_monthly_debts cannot be negative")

    transactions = _transactions_for_recurring(get_transactions(db, uid))
    income_info = estimate_annual_income(transactions)
    if income_info["estimated_annual_income"] <= 0:
        raise HTTPException(
            status_code=400,
            detail="Not enough recurring income history yet - sync more transaction history first.",
        )

    rates = fetch_mortgage_rates()
    default_rate = next(
        (r["rate_decimal"] for r in rates if r["label"] == "30_year_fixed"),
        rates[0]["rate_decimal"] if rates else 0.065,
    )
    state = _infer_state(payload.location, load_property_tax_insurance())
    default_tax_rate = state["property_tax_rate"] if state else 0.011
    default_insurance = state["avg_annual_homeowners_insurance"] if state else 1500.0

    interest_rate = payload.interest_rate if payload.interest_rate is not None else default_rate
    property_tax_rate = payload.property_tax_rate if payload.property_tax_rate is not None else default_tax_rate
    insurance_estimate = (
        payload.annual_insurance_estimate if payload.annual_insurance_estimate is not None else default_insurance
    )

    result = housing_affordability(
        income=income_info["estimated_annual_income"],
        price=payload.price,
        down_payment=payload.down_payment,
        interest_rate=interest_rate,
        property_tax_rate=property_tax_rate,
        insurance_estimate=insurance_estimate,
        loan_term_months=payload.loan_term_months,
        other_monthly_debts=payload.other_monthly_debts,
    )

    return HomeAffordabilityResponse(
        **result,
        estimated_annual_income=income_info["estimated_annual_income"],
        income_sources=income_info["income_sources"],
        other_monthly_debts=payload.other_monthly_debts,
        interest_rate_used=interest_rate,
        property_tax_rate_used=property_tax_rate,
        annual_insurance_estimate_used=insurance_estimate,
        retrieved_facts=_housing_context(payload.location),
    )


@app.post("/budget/recommend", response_model=RecommendBudgetResponse)
def recommend_budget(
    payload: RecommendBudgetRequest,
    decoded_token: dict = Depends(require_firebase_auth),
    db: DbSession = Depends(get_db),
) -> RecommendBudgetResponse:
    uid = decoded_token["uid"]
    _check_recommend_rate_limit(uid)

    transactions = get_transactions(db, uid)
    budgets = get_budgets(db, uid)
    result = recommend_budgets(
        _transactions_as_dicts(transactions), budgets, months=payload.months, target_total=payload.target_total
    )
    return RecommendBudgetResponse(
        recommendations=result["recommendations"],
        summary=result["summary"],
        source=result["source"],
    )


@app.post("/goals", response_model=GoalOut)
def create_goal_endpoint(
    payload: CreateGoalRequest,
    decoded_token: dict = Depends(require_firebase_auth),
    db: DbSession = Depends(get_db),
) -> GoalOut:
    uid = decoded_token["uid"]
    _reject_if_demo(uid)
    if payload.target_amount <= 0:
        raise HTTPException(status_code=400, detail="target_amount must be positive")

    budgets, transactions = _budgets_and_transactions(db, uid)
    capacity = compute_monthly_savings_capacity(budgets, transactions)
    goal = create_goal(
        db,
        uid,
        payload.name,
        payload.target_amount,
        payload.category,
        capacity,
        target_date=payload.target_date,
        current_saved=payload.current_saved,
    )
    return _goal_out(goal, budgets, transactions)


@app.get("/goals", response_model=list[GoalOut])
def list_goals(
    status: Optional[str] = "active",
    decoded_token: dict = Depends(require_firebase_auth),
    db: DbSession = Depends(get_db),
) -> list[GoalOut]:
    uid = decoded_token["uid"]
    goals = get_goals(db, uid, status=status)
    budgets, transactions = _budgets_and_transactions(db, uid)
    return [_goal_out(goal, budgets, transactions) for goal in goals]


@app.get("/goals/{goal_id}/health", response_model=GoalHealthOut)
def get_goal_health(
    goal_id: int,
    decoded_token: dict = Depends(require_firebase_auth),
    db: DbSession = Depends(get_db),
) -> GoalHealthOut:
    uid = decoded_token["uid"]
    goal = get_goal(db, uid, goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    budgets, transactions = _budgets_and_transactions(db, uid)
    return GoalHealthOut(**check_goal_health(_goal_as_dict(goal), budgets, transactions))


@app.get("/goals/{goal_id}/auto-budget", response_model=AutoBudgetOut)
def get_auto_budget(
    goal_id: int,
    location: Optional[str] = None,
    decoded_token: dict = Depends(require_firebase_auth),
    db: DbSession = Depends(get_db),
) -> AutoBudgetOut:
    uid = decoded_token["uid"]
    goal = get_goal(db, uid, goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")

    _check_auto_budget_rate_limit(uid)

    budgets, transactions = _budgets_and_transactions(db, uid)
    required_cut = required_additional_capacity(_goal_as_dict(goal), budgets, transactions)
    profile = spending_profile(transactions)
    # location is optional and client-supplied (this app has no stored user
    # profile) - retrieve_housing_context still returns current national
    # mortgage-rate facts unconditionally either way, and adds local
    # property-tax/cost-of-living facts only when a city is given.
    housing_facts = _housing_context(location) if "Housing" in profile else None

    result = recommend_budget_for_goal(goal.name, required_cut, profile, budgets, housing_facts)
    return AutoBudgetOut(
        required_cut=required_cut,
        suggestions=[CategoryBudgetSuggestionOut(**s) for s in result["suggestions"]],
        summary=result["summary"],
        source=result["source"],
    )


@app.patch("/goals/{goal_id}", response_model=GoalOut)
def update_goal_endpoint(
    goal_id: int,
    payload: UpdateGoalRequest,
    decoded_token: dict = Depends(require_firebase_auth),
    db: DbSession = Depends(get_db),
) -> GoalOut:
    uid = decoded_token["uid"]
    _reject_if_demo(uid)
    fields = {key: value for key, value in payload.model_dump().items() if value is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    if "target_amount" in fields and fields["target_amount"] <= 0:
        raise HTTPException(status_code=400, detail="target_amount must be positive")

    goal = update_goal(db, uid, goal_id, **fields)
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    budgets, transactions = _budgets_and_transactions(db, uid)
    return _goal_out(goal, budgets, transactions)


@app.delete("/goals/{goal_id}", response_model=GoalActionResponse)
def delete_goal_endpoint(
    goal_id: int,
    decoded_token: dict = Depends(require_firebase_auth),
    db: DbSession = Depends(get_db),
) -> GoalActionResponse:
    uid = decoded_token["uid"]
    _reject_if_demo(uid)
    goal = abandon_goal(db, uid, goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    return GoalActionResponse(status="abandoned")


@app.get("/recurring", response_model=list[RecurringChargeOut])
def get_recurring(
    decoded_token: dict = Depends(require_firebase_auth),
    db: DbSession = Depends(get_db),
) -> list[RecurringChargeOut]:
    uid = decoded_token["uid"]
    transactions = get_transactions(db, uid)
    charges = detect_recurring_charges(_transactions_for_recurring(transactions))

    status = _current_status(db, uid)
    active_goals = get_goals(db, uid, status="active")
    budgets, all_transactions = _budgets_and_transactions(db, uid)

    results = []
    for charge in charges:
        # A recurring charge is an ongoing monthly commitment, not a one-time
        # purchase - check it against the budget the same way a "monthly"
        # timing purchase would be, so the verdict reflects it recurring
        # every month rather than just this one time.
        verdict = check_purchase(status, charge["average_amount"], charge["category"], "monthly")["verdict"]

        impact_on_goals = None
        if active_goals:
            impact_on_goals = []
            for goal in active_goals:
                impact = redirect_impact(_goal_as_dict(goal), charge["average_amount"], budgets, all_transactions)
                if impact is not None:
                    impact_on_goals.append(
                        RecurringGoalImpactOut(goal_id=goal.id, goal_name=goal.name, **impact)
                    )
        results.append(RecurringChargeOut(**charge, verdict=verdict, impact_on_goals=impact_on_goals))
    return results
