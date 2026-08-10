"""Deterministic savings-goal math: turning a not-yet-affordable purchase
into a tracked goal, and checking whether actual spending pace is keeping it
on track. No LLM here - see app/explain.py for the pattern an optional
plain-language layer on top of this would follow (pre-computed facts in,
one short sentence out).

This app has no income tracking - it only knows Plaid-synced transactions
and user-set category budgets. So "monthly savings capacity" here means
average monthly budget headroom (total budgeted minus total actually spent,
across every category with a budget set), not true income-minus-expenses.
It's the closest deterministic proxy available from this app's real data,
not a stand-in for the "income/expense estimation" a from-scratch income
tracker would need - this app doesn't have one.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Optional

from app.budget import spending_trend

CAPACITY_MONTHS = 3

# How far actual pace can fall below (or rise above) the planned pace before
# a goal is flagged behind/ahead - a buffer so ordinary month-to-month noise
# doesn't trip a warning (or a false "ahead!") every time spending wobbles.
BEHIND_PACE_THRESHOLD = 0.85
AHEAD_PACE_THRESHOLD = 1.15


def compute_monthly_savings_capacity(budgets: dict, transactions: list, months: int = CAPACITY_MONTHS) -> float:
    """Average monthly (total budgeted - total actually spent) across every
    budgeted category, over the last `months` calendar months present in
    `transactions`. This is the deterministic seed for a new goal's plan,
    and is recomputed the same way later to check actual pace against it."""
    total_budget = sum(v for v in budgets.values() if v is not None)
    if total_budget == 0:
        return 0.0

    trend = spending_trend(transactions, months)
    observed_months = trend["months"]
    if not observed_months:
        return 0.0

    budgeted_categories = [c for c, v in budgets.items() if v is not None]
    surplus_by_month = []
    for month in observed_months:
        actual_this_month = sum(
            trend["by_category"].get(category, {}).get(month, 0.0) for category in budgeted_categories
        )
        surplus_by_month.append(total_budget - actual_this_month)

    return round(sum(surplus_by_month) / len(surplus_by_month), 2)


def compute_savings_plan(target_amount: float, current_saved: float, monthly_savings_capacity: float) -> dict:
    """The initial plan for a new goal: how much is left to save and roughly
    how long it should take at the computed capacity. months_to_goal is
    fractional - callers round up for display."""
    gap = round(max(target_amount - current_saved, 0.0), 2)
    if gap == 0:
        months_to_goal = 0.0
    elif monthly_savings_capacity <= 0:
        months_to_goal = None  # no capacity, no plan - not "never", just unknown
    else:
        months_to_goal = round(gap / monthly_savings_capacity, 2)

    return {
        "gap": gap,
        "monthly_savings_capacity": monthly_savings_capacity,
        "months_to_goal": months_to_goal,
    }


def plan_from_affordability_check(price: float, budgets: dict, transactions: list) -> dict:
    """Seeds a goal's plan from an existing check_purchase() result (see
    app.affordability) when the user chooses to "track this as a goal"
    after a not-affordable verdict - reuses the same budget/spend math via
    compute_monthly_savings_capacity, no duplicated logic."""
    monthly_savings_capacity = compute_monthly_savings_capacity(budgets, transactions)
    return compute_savings_plan(target_amount=price, current_saved=0.0, monthly_savings_capacity=monthly_savings_capacity)


def _add_months(start: date, months: float) -> str:
    """Approximates a date `months` (fractional, rounded up) out from
    `start`. This app only ever displays completion dates to the nearest
    month, so calendar-day precision isn't needed."""
    whole_months = math.ceil(months)
    total = start.month - 1 + whole_months
    year = start.year + total // 12
    month = total % 12 + 1
    return date(year, month, 1).isoformat()


def check_goal_health(goal: dict, budgets: dict, transactions: list, today: Optional[date] = None) -> dict:
    """Compares a goal's original planned pace (monthly_savings_capacity,
    captured at creation time) against the *current* actual pace, computed
    the same way from recent transactions. Falling meaningfully behind the
    plan - especially concentrated in the goal's own category - is what
    triggers a warning; a small dip is normal and not flagged.

    `goal` is a plain dict with target_amount, current_saved, category,
    monthly_savings_capacity, and optionally target_date (ISO string).

    Returns: on_track (bool), pace_status ("ahead"|"on_pace"|"behind"),
    projected_shortfall (float), projected_completion_date (ISO str or
    None), reason (short structured string a UI or optional LLM layer can
    key off, e.g. "entertainment_overspend", "general_overspend", "on_pace").
    """
    today = today or date.today()
    gap = round(goal["target_amount"] - goal["current_saved"], 2)

    if gap <= 0:
        return {
            "on_track": True,
            "pace_status": "on_pace",
            "projected_shortfall": 0.0,
            "projected_completion_date": None,
            "reason": "goal_achieved",
        }

    planned_capacity = goal["monthly_savings_capacity"]
    current_capacity = compute_monthly_savings_capacity(budgets, transactions)

    category = goal["category"]
    category_budget = budgets.get(category)
    trend = spending_trend(transactions, months=CAPACITY_MONTHS)
    observed_months = trend["months"]
    category_actuals = trend["by_category"].get(category, {})
    recent_category_avg = (
        round(sum(category_actuals.get(m, 0.0) for m in observed_months) / len(observed_months), 2)
        if observed_months
        else 0.0
    )
    category_overspend = round(recent_category_avg - category_budget, 2) if category_budget is not None else None

    pace_ratio = (current_capacity / planned_capacity) if planned_capacity > 0 else 0.0

    if pace_ratio >= AHEAD_PACE_THRESHOLD:
        pace_status = "ahead"
    elif pace_ratio >= BEHIND_PACE_THRESHOLD:
        pace_status = "on_pace"
    else:
        pace_status = "behind"

    on_track = pace_status != "behind"

    if pace_status == "behind":
        capacity_drop = planned_capacity - current_capacity
        # If the goal's own category accounts for at least half the total
        # capacity drop, name that category specifically - otherwise it's a
        # broader pullback not concentrated in one place.
        if category_overspend is not None and category_overspend > 0 and category_overspend >= capacity_drop * 0.5:
            reason = f"{category.lower()}_overspend"
        else:
            reason = "general_overspend"
    elif pace_status == "ahead":
        reason = "ahead_of_pace"
    else:
        reason = "on_pace"

    projected_completion_date = _add_months(today, gap / current_capacity) if current_capacity > 0 else None

    projected_shortfall = 0.0
    if goal.get("target_date"):
        target = date.fromisoformat(goal["target_date"])
        months_until_target = max((target.year - today.year) * 12 + (target.month - today.month), 0)
        projected_saved_by_target = goal["current_saved"] + max(current_capacity, 0.0) * months_until_target
        projected_shortfall = round(max(goal["target_amount"] - projected_saved_by_target, 0.0), 2)
    elif pace_status == "behind":
        # No target date to measure against - express the shortfall as the
        # monthly gap between what was planned and what's actually happening.
        projected_shortfall = round(max(planned_capacity - current_capacity, 0.0), 2)

    return {
        "on_track": on_track,
        "pace_status": pace_status,
        "projected_shortfall": projected_shortfall,
        "projected_completion_date": projected_completion_date,
        "reason": reason,
    }
