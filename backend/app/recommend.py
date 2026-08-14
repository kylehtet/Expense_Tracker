"""AI-recommended monthly budgets. The spending stats given to the model are
computed deterministically from app.budget.spending_trend; the LLM only reasons
about what to recommend from those real numbers - it's told not to invent a
spending figure, only to propose and justify a budget amount."""

from __future__ import annotations

import anthropic
from pydantic import BaseModel

from app import llm_cache
from app.budget import spending_trend
from app.llm_metrics import log_usage

MODEL = "claude-sonnet-5"
FEATURE = "recommend_budgets"

SYSTEM_PROMPT = (
    "Recommend a monthly budget per category using only the given real spend "
    "numbers - never invent a figure. Propose a round number near the average, "
    "nudged up if spend is rising or volatile, rounded to the nearest $5-$10. "
    "Omit categories with no history. One short, concrete rationale per "
    "category referencing the actual numbers. If a total monthly target is "
    "given, the categories should collectively add up to roughly that amount - "
    "cut discretionary categories (Entertainment, Subscriptions, Shopping, Other, Food) "
    "before fixed ones (Housing, Transport) if the target requires trimming "
    "below historical average spend."
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
        # The SDK's default timeout is minutes long - too slow to sit behind a
        # "fill in the boxes" click. Short-circuit to the deterministic
        # fallback below well before the user notices, on any network hiccup.
        _client = anthropic.Anthropic(timeout=20.0)
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


def _build_user_message(profile: dict, current_budgets: dict, target_total: float | None) -> str:
    lines = ["Spending history by category (months with $0 spend excluded):"]
    for category, stats in profile.items():
        current = current_budgets.get(category)
        budget_note = f", current budget ${current}" if current is not None else ", no budget set yet"
        lines.append(
            f"- {category}: average ${stats['average']}/mo over {stats['months_observed']} month(s), "
            f"range ${stats['min']}-${stats['max']}, most recent month ${stats['most_recent']}{budget_note}"
        )
    if target_total is not None:
        lines.append(f"\nTotal monthly budget target across all categories: ${target_total:.2f}.")
    lines.append("\nRecommend a monthly budget for each category listed above.")
    return "\n".join(lines)


_DISCRETIONARY_PRIORITY = ["Entertainment", "Subscriptions", "Shopping", "Other", "Food", "Transport", "Housing"]


def _rescale_to_target(recommendations: list[dict], target_total: float) -> list[dict]:
    """Guarantees the recommendations collectively sum to target_total, scaling
    every category proportionally to its proposed share rather than trusting
    the model's own arithmetic - same "model proposes, code guarantees the
    number" pattern as app.auto_budget._rescale_to_meet_target. Applied to
    both the AI and fallback paths, so the target is honored either way."""
    total = sum(r["recommended_budget"] for r in recommendations)
    if total <= 0 or round(total, 2) == round(target_total, 2):
        return recommendations
    scale = target_total / total
    ordered = sorted(
        recommendations,
        key=lambda r: _DISCRETIONARY_PRIORITY.index(r["category"]) if r["category"] in _DISCRETIONARY_PRIORITY else len(_DISCRETIONARY_PRIORITY),
    )
    return [{**r, "recommended_budget": round(r["recommended_budget"] * scale, 2)} for r in ordered]


def _fallback_recommendations(profile: dict, target_total: float | None) -> dict:
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
    if target_total is not None:
        recommendations = _rescale_to_target(recommendations, target_total)
    return {
        "recommendations": recommendations,
        "summary": "Based on your recent average spend per category, rounded up slightly for headroom.",
    }


def recommend_budgets(
    transactions: list, current_budgets: dict, months: int = 6, target_total: float | None = None
) -> dict:
    profile = spending_profile(transactions, months)
    if not profile:
        return {
            "recommendations": [],
            "summary": "Not enough spending history yet to recommend budgets.",
            "source": "none",
            "error": None,
        }

    key = llm_cache.cache_key(FEATURE, profile, current_budgets, target_total)
    cached = llm_cache.get(key)
    if cached is not None:
        log_usage(FEATURE, MODEL, input_tokens=0, output_tokens=0, cached=True)
        return cached

    try:
        response = _get_client().messages.parse(
            model=MODEL,
            max_tokens=800,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _build_user_message(profile, current_budgets, target_total)}],
            output_format=BudgetRecommendations,
        )
        parsed = response.parsed_output
        log_usage(FEATURE, MODEL, response.usage.input_tokens, response.usage.output_tokens)
        recommendations = [r.model_dump() for r in parsed.recommendations if r.recommended_budget > 0]
        if target_total is not None:
            recommendations = _rescale_to_target(recommendations, target_total)
        result = {
            "recommendations": recommendations,
            "summary": parsed.summary,
            "source": "ai",
            "error": None,
        }
        llm_cache.set(key, result)
        return result
    except Exception as exc:
        result = _fallback_recommendations(profile, target_total)
        result["source"] = "fallback"
        result["error"] = str(exc)
        return result
