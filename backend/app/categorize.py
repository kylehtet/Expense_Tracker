"""Maps Plaid's transaction categories into a simpler internal taxonomy."""

from __future__ import annotations

INTERNAL_CATEGORIES = ("Housing", "Food", "Transport", "Subscriptions", "Entertainment", "Other")

# Plaid's personal_finance_category.primary values (per plaid.com/documents/pfc-taxonomy-all.csv)
# that map cleanly onto our taxonomy. Anything absent from this map falls back to "Other".
_PRIMARY_CATEGORY_MAP = {
    "RENT_AND_UTILITIES": "Housing",
    "HOME_IMPROVEMENT": "Housing",
    "FOOD_AND_DRINK": "Food",
    "TRANSPORTATION": "Transport",
    "TRAVEL": "Transport",
    "ENTERTAINMENT": "Entertainment",
}

# Plaid's taxonomy has no distinct "subscription" category - streaming services
# fall under ENTERTAINMENT and other subscriptions under GENERAL_SERVICES, so
# recurring services are detected by known merchant name instead. This is
# exactly the kind of mis-labeling categorize_with_llm is meant to catch later.
_SUBSCRIPTION_MERCHANT_KEYWORDS = (
    "netflix",
    "spotify",
    "hulu",
    "disney+",
    "disney plus",
    "hbo max",
    "amazon prime",
    "youtube premium",
    "apple music",
    "apple tv",
    "paramount+",
    "peacock",
    "adobe",
    "dropbox",
    "icloud",
    "github",
    "notion",
    "audible",
    "xbox game pass",
    "playstation plus",
)


def categorize_transaction(transaction: dict) -> str:
    merchant = (transaction.get("merchant_name") or transaction.get("name") or "").lower()
    if any(keyword in merchant for keyword in _SUBSCRIPTION_MERCHANT_KEYWORDS):
        return "Subscriptions"

    primary = (transaction.get("personal_finance_category") or {}).get("primary")
    return _PRIMARY_CATEGORY_MAP.get(primary, "Other")


def categorize_with_llm(transaction: dict) -> str:
    """Hook for an LLM-based re-categorization pass over transactions the rules
    above mis-label (e.g. non-streaming subscriptions with no keyword match).
    Not implemented in the rules-based-first build."""
    raise NotImplementedError("LLM-based re-categorization is not implemented yet")
