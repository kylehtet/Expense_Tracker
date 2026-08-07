"""Deterministic budgeting calculations over categorized transactions. No LLM."""

from __future__ import annotations

from app.categorize import categorize_transaction

# actual/budget ratio at or above which a category counts as "on_track"
# rather than "under", even though it hasn't gone over.
ON_TRACK_THRESHOLD = 0.9


def _month_key(date_value) -> str:
    if hasattr(date_value, "strftime"):
        return date_value.strftime("%Y-%m")
    return str(date_value)[:7]


def monthly_spend_by_category(transactions: list) -> dict:
    """Net spend per internal category for the given transactions (Plaid sign
    convention: positive amount = money out, negative = money in, so refunds
    and deposits net against spend). Callers pass in one period's worth of
    transactions - this doesn't group by calendar month; see spending_trend."""
    spend: dict[str, float] = {}
    for txn in transactions:
        category = categorize_transaction(txn)
        spend[category] = spend.get(category, 0.0) + float(txn["amount"])
    return {category: round(total, 2) for category, total in spend.items()}


def budget_status(category_budgets: dict, actual_spend: dict) -> dict:
    """Per-category over/on_track/under status. Categories with spend but no
    budget set are flagged "unbudgeted" rather than silently dropped."""
    status: dict[str, dict] = {}
    for category in set(category_budgets) | set(actual_spend):
        budget = category_budgets.get(category)
        actual = actual_spend.get(category, 0.0)

        if budget is None:
            status[category] = {
                "budget": None,
                "actual": round(actual, 2),
                "remaining": None,
                "pct_used": None,
                "status": "unbudgeted",
            }
            continue

        remaining = budget - actual
        if budget > 0:
            pct_used = actual / budget
        else:
            pct_used = None if actual <= 0 else float("inf")

        if actual > budget:
            category_status = "over"
        elif pct_used is not None and pct_used >= ON_TRACK_THRESHOLD:
            category_status = "on_track"
        else:
            category_status = "under"

        status[category] = {
            "budget": round(budget, 2),
            "actual": round(actual, 2),
            "remaining": round(remaining, 2),
            "pct_used": round(pct_used, 4) if pct_used not in (None, float("inf")) else None,
            "status": category_status,
        }
    return status


def spending_trend(transactions: list, months: int) -> dict:
    """Per-category monthly totals for the most recent `months` calendar
    months present in `transactions`, plus the month-over-month change for
    the most recent pair of months."""
    monthly_totals: dict[str, dict[str, float]] = {}
    for txn in transactions:
        month = _month_key(txn["date"])
        category = categorize_transaction(txn)
        bucket = monthly_totals.setdefault(month, {})
        bucket[category] = bucket.get(category, 0.0) + float(txn["amount"])

    sorted_months = sorted(monthly_totals)[-months:]
    categories = sorted({c for m in sorted_months for c in monthly_totals[m]})

    by_category = {
        category: {
            month: round(monthly_totals[month].get(category, 0.0), 2) for month in sorted_months
        }
        for category in categories
    }

    change_from_previous_month: dict[str, dict] = {}
    if len(sorted_months) >= 2:
        previous_month, current_month = sorted_months[-2], sorted_months[-1]
        for category in categories:
            previous = monthly_totals[previous_month].get(category, 0.0)
            current = monthly_totals[current_month].get(category, 0.0)
            change = current - previous
            if previous:
                change_pct = round(change / previous * 100, 2)
            else:
                change_pct = None if change == 0 else float("inf")
            change_from_previous_month[category] = {
                "previous": round(previous, 2),
                "current": round(current, 2),
                "change": round(change, 2),
                "change_pct": change_pct if change_pct != float("inf") else None,
            }

    return {
        "months": sorted_months,
        "by_category": by_category,
        "change_from_previous_month": change_from_previous_month,
    }
