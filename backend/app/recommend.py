"""AI-recommended monthly budgets. The spending stats given to the model are
computed deterministically from app.budget.spending_trend; the LLM only reasons
about what to recommend from those real numbers - it's told not to invent a
spending figure, only to propose and justify a budget amount."""

from __future__ import annotations

import anthropic
from pydantic import BaseModel

from app.budget import spending_trend

MODEL = "claude-sonnet-5"

SYSTEM_PROMPT = (
    "You recommend monthly budget limits for a personal finance app, one per "
    "category. You are given each category's real spend for the last several "
    "months - use only those numbers, never invent a spending figure. For each "
    "category, propose a sensible round-number monthly budget: usually close to "
    "the average, nudged up if spending is trending up or highly variable so the "
    "budget isn't unrealistically tight, and rounded to a number a person would "
    "actually type (nearest $5 or $10, not $266.14). If a category has no "
    "spending history, omit it rather than guessing. Keep each rationale to one "
    "short, concrete sentence referencing the actual numbers you were given."
)


class CategoryRecommendation(BaseModel):
    category: str
    recommended_budget: float
    rationale: str


class BudgetRecommendations(BaseModel):
    recommendations: list[CategoryRecommendation]
    summary: str


_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def spending_profile(transactions: list, months: int = 6) -> dict:
    """Per-category average/min/max/most-recent monthly spend over the last
    `months` calendar months present in `transactions`. Categories with no
    spend in any of those months are omitted - nothing to recommend from."""
    trend = spending_trend(transactions, months)
    profile: dict[str, dict] = {}
    for category, by_month in trend["by_category"].items():
        # Filter out zero/negative (refund-heavy) months before taking
        # stats, then take "most recent" from that same filtered, chronologically-
        # sorted set - otherwise a refund month can report a "most recent" spend
        # that falls outside the min/max range computed from the real spend months.
        positive_months = [(month, v) for month, v in sorted(by_month.items()) if v > 0]
        if not positive_months:
            continue
        values = [v for _, v in positive_months]
        profile[category] = {
            "months_observed": len(values),
            "average": round(sum(values) / len(values), 2),
            "min": round(min(values), 2),
            "max": round(max(values), 2),
            "most_recent": round(positive_months[-1][1], 2),
        }
    return profile


def _build_user_message(profile: dict, current_budgets: dict) -> str:
    lines = ["Spending history by category (months with $0 spend excluded):"]
    for category, stats in profile.items():
        current = current_budgets.get(category)
        budget_note = f", current budget ${current}" if current is not None else ", no budget set yet"
        lines.append(
            f"- {category}: average ${stats['average']}/mo over {stats['months_observed']} month(s), "
            f"range ${stats['min']}-${stats['max']}, most recent month ${stats['most_recent']}{budget_note}"
        )
    lines.append("\nRecommend a monthly budget for each category listed above.")
    return "\n".join(lines)


def _fallback_recommendations(profile: dict) -> dict:
    """Used only if the Anthropic call fails - round the higher of the average
    or most-recent month up to the nearest $10, so an outage never blocks
    getting *some* suggestion."""
    recommendations = []
    for category, stats in profile.items():
        base = max(stats["average"], stats["most_recent"])
        rounded = (int(base // 10) + 1) * 10
        recommendations.append(
            {
                "category": category,
                "recommended_budget": float(rounded),
                "rationale": f"About ${stats['average']}/mo on average recently, rounded up for headroom.",
            }
        )
    return {
        "recommendations": recommendations,
        "summary": "Based on your recent average spend per category, rounded up slightly for headroom.",
    }


def recommend_budgets(transactions: list, current_budgets: dict, months: int = 6) -> dict:
    profile = spending_profile(transactions, months)
    if not profile:
        return {
            "recommendations": [],
            "summary": "Not enough spending history yet to recommend budgets.",
            "source": "none",
            "error": None,
        }

    try:
        response = _get_client().messages.parse(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _build_user_message(profile, current_budgets)}],
            output_format=BudgetRecommendations,
        )
        parsed = response.parsed_output
        return {
            "recommendations": [r.model_dump() for r in parsed.recommendations if r.recommended_budget > 0],
            "summary": parsed.summary,
            "source": "ai",
            "error": None,
        }
    except Exception as exc:
        result = _fallback_recommendations(profile)
        result["source"] = "fallback"
        result["error"] = str(exc)
        return result
