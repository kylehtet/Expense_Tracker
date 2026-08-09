"""Deterministic "can I afford this?" math over an existing budget_status. No LLM -
the verdict and every number here are arithmetic on real budgets; only the plain-
language explanation (explain.py) touches an LLM, and it's told not to invent numbers."""

from __future__ import annotations

import calendar
from datetime import date

TIMINGS = ("one_time", "monthly", "split_3")


def _effective_amount(price: float, timing: str) -> float:
    return price / 3 if timing == "split_3" else price


def check_purchase(status: dict, price: float, category: str, timing: str, today: date | None = None) -> dict:
    if timing not in TIMINGS:
        raise ValueError(f"Unknown timing '{timing}'; expected one of {TIMINGS}")

    today = today or date.today()
    effective_amount = _effective_amount(price, timing)

    entry = status.get(category, {})
    category_budget = entry.get("budget")
    category_actual = entry.get("actual", 0.0)
    category_left_before = None if category_budget is None else round(category_budget - category_actual, 2)
    category_left_after = None if category_left_before is None else round(category_left_before - effective_amount, 2)

    has_any_budget = any(e.get("budget") is not None for e in status.values())
    overall_left_before = round(sum(e["remaining"] for e in status.values() if e.get("budget") is not None), 2)
    overall_left_after = round(overall_left_before - effective_amount, 2)

    if category_left_after is None:
        # No budget set for this category. With no budget set anywhere, there's
        # nothing to measure the purchase against - don't call that "over".
        if not has_any_budget:
            verdict = "comfortable"
        else:
            verdict = "comfortable" if overall_left_after >= 0 else "over"
    elif category_left_after >= 0 and overall_left_after >= 0:
        verdict = "comfortable"
    elif overall_left_after >= 0:
        verdict = "tight"
    else:
        verdict = "over"

    days_in_month = calendar.monthrange(today.year, today.month)[1]
    days_remaining = days_in_month - today.day + 1
    total_spent_so_far = round(sum(e.get("actual", 0.0) for e in status.values()), 2)
    current_daily_pace = round(total_spent_so_far / today.day, 2) if today.day > 0 else 0.0
    projected_daily_pace = round((total_spent_so_far + effective_amount) / today.day, 2) if today.day > 0 else 0.0
    effect_on_pace_pct = (
        round((projected_daily_pace / current_daily_pace - 1) * 100, 1) if current_daily_pace > 0 else None
    )
    safe_to_spend_today = round(overall_left_before / days_remaining, 2) if days_remaining > 0 else overall_left_before

    return {
        "verdict": verdict,
        "category": category,
        "price": round(price, 2),
        "timing": timing,
        "effective_amount": round(effective_amount, 2),
        "split_monthly": round(price / 3, 2),
        "category_left_before": category_left_before,
        "category_left_after": category_left_after,
        "overall_left_before": overall_left_before,
        "overall_left_after": overall_left_after,
        "days_remaining": days_remaining,
        "current_daily_pace": current_daily_pace,
        "safe_to_spend_today": safe_to_spend_today,
        "effect_on_pace_pct": effect_on_pace_pct,
    }
