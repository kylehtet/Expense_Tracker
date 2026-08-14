"""Deterministic recurring-income detection over synced transaction history.
No LLM. Reuses app.recurring's chain-matching algorithm - a recurring paycheck
is structurally the same pattern as a recurring charge (same merchant, similar
amount, landing on a regular interval), just on the opposite side of Plaid's
sign convention: positive amount is money leaving the account, negative is
money coming in.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Optional

from app.recurring import LOOKBACK_MONTHS, _longest_recurring_chain, _normalize_merchant, _parse_date

MIN_OCCURRENCES = 2

# Paycheck cadences run from weekly through monthly - a wider window than
# app.recurring's 25-35 day (subscription-only) default.
MIN_INTERVAL_DAYS = 5
MAX_INTERVAL_DAYS = 35


def detect_recurring_income(
    transactions: list[dict], months: int = LOOKBACK_MONTHS, today: Optional[date] = None
) -> list[dict]:
    """Groups transactions by normalized merchant/payer name and flags any
    payer with 2+ deposits of a similar amount landing on a roughly regular
    interval. Returns one entry per detected income stream, largest first."""
    today = today or date.today()
    cutoff = today - timedelta(days=months * 30)

    by_payer: dict[str, list[dict]] = defaultdict(list)
    for txn in transactions:
        amount = float(txn["amount"])
        if amount >= 0:
            continue  # only deposits (Plaid: negative amount = money in)
        txn_date = _parse_date(txn["date"])
        if txn_date < cutoff:
            continue
        key = _normalize_merchant(txn)
        if not key:
            continue
        by_payer[key].append({**txn, "amount": abs(amount), "_date": txn_date})

    results = []
    for key, txns in by_payer.items():
        txns.sort(key=lambda t: t["_date"])
        chain = _longest_recurring_chain(txns, MIN_INTERVAL_DAYS, MAX_INTERVAL_DAYS)
        if len(chain) < MIN_OCCURRENCES:
            continue

        amounts = [float(t["amount"]) for t in chain]
        avg_amount = round(sum(amounts) / len(amounts), 2)
        intervals = [(chain[i]["_date"] - chain[i - 1]["_date"]).days for i in range(1, len(chain))]
        avg_interval = round(sum(intervals) / len(intervals)) if intervals else 30
        last = chain[-1]
        display_name = (last.get("merchant_name") or last.get("name") or key).strip()

        results.append(
            {
                "source": display_name,
                "average_amount": avg_amount,
                "average_interval_days": avg_interval,
                "occurrences": len(chain),
                "last_received": last["_date"].isoformat(),
            }
        )

    results.sort(key=lambda r: r["average_amount"], reverse=True)
    return results


def _periods_per_year(average_interval_days: int) -> int:
    if average_interval_days <= 10:
        return 52  # weekly
    if average_interval_days <= 20:
        return 26  # biweekly
    return 12  # monthly (also the fallback for anything longer)


def estimate_annual_income(
    transactions: list[dict], months: int = LOOKBACK_MONTHS, today: Optional[date] = None
) -> dict:
    """Sums every detected recurring income stream's own annualized amount,
    inferring pay frequency from its own average interval so a weekly and a
    monthly deposit aren't both annualized as if they were monthly."""
    sources = detect_recurring_income(transactions, months, today)
    enriched = []
    total = 0.0
    for source in sources:
        periods = _periods_per_year(source["average_interval_days"])
        annual = round(source["average_amount"] * periods, 2)
        total += annual
        enriched.append({**source, "periods_per_year": periods, "estimated_annual": annual})

    return {"estimated_annual_income": round(total, 2), "income_sources": enriched}
