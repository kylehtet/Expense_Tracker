"""Deterministic recurring-charge detection over synced transaction history.
No LLM - a merchant is "recurring" purely by amount/interval pattern-matching,
the same rules-first approach as budget.py and goal_tracker.py.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Optional

MIN_OCCURRENCES = 2
AMOUNT_TOLERANCE_PCT = 0.05
MIN_INTERVAL_DAYS = 25
MAX_INTERVAL_DAYS = 35
LOOKBACK_MONTHS = 6


def _normalize_merchant(txn: dict) -> str:
    raw = txn.get("merchant_name") or txn.get("name") or ""
    return " ".join(raw.strip().lower().split())


def _parse_date(value) -> date:
    if hasattr(value, "year"):
        return value
    return date.fromisoformat(str(value)[:10])


def _longest_recurring_chain(sorted_txns: list[dict]) -> list[dict]:
    """Longest run of transactions (in date order) that plausibly reads as one
    subscription: each new charge lands 25-35 days after the previous one
    kept in the chain, and its amount is within ~5% of the chain's average so
    far (so a slowly-drifting bill like a utility still matches, rather than
    requiring every step to be within tolerance of the one immediately before
    it). Tries every possible start so one noisy/unrelated transaction from
    the same merchant doesn't sink an otherwise-clean chain."""
    best: list[dict] = []
    n = len(sorted_txns)
    for start in range(n):
        chain = [sorted_txns[start]]
        for i in range(start + 1, n):
            candidate = sorted_txns[i]
            days = (candidate["_date"] - chain[-1]["_date"]).days
            if days < MIN_INTERVAL_DAYS:
                continue
            if days > MAX_INTERVAL_DAYS:
                break
            chain_avg = sum(float(t["amount"]) for t in chain) / len(chain)
            if chain_avg <= 0 or abs(float(candidate["amount"]) - chain_avg) / chain_avg > AMOUNT_TOLERANCE_PCT:
                continue
            chain.append(candidate)
        if len(chain) > len(best):
            best = chain
    return best


def detect_recurring_charges(
    transactions: list[dict], months: int = LOOKBACK_MONTHS, today: Optional[date] = None
) -> list[dict]:
    """Groups transactions by normalized merchant name and flags any merchant
    with 2+ charges of a similar amount landing roughly monthly apart.
    Returns one entry per detected recurring charge, most recently charged
    first."""
    today = today or date.today()
    cutoff = today - timedelta(days=months * 30)

    by_merchant: dict[str, list[dict]] = defaultdict(list)
    for txn in transactions:
        amount = float(txn["amount"])
        if amount <= 0:
            continue  # refunds/deposits aren't a charge
        txn_date = _parse_date(txn["date"])
        if txn_date < cutoff:
            continue
        key = _normalize_merchant(txn)
        if not key:
            continue
        by_merchant[key].append({**txn, "_date": txn_date})

    results = []
    for key, txns in by_merchant.items():
        txns.sort(key=lambda t: t["_date"])
        chain = _longest_recurring_chain(txns)
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
                "merchant": display_name,
                "average_amount": avg_amount,
                "category": last.get("category", "Other"),
                "occurrences": len(chain),
                "first_seen": chain[0]["_date"].isoformat(),
                "last_charged": last["_date"].isoformat(),
                "next_charge_estimate": (last["_date"] + timedelta(days=avg_interval)).isoformat(),
            }
        )

    results.sort(key=lambda r: r["last_charged"], reverse=True)
    return results
