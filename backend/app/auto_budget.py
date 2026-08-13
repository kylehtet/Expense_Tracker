"""LLM-assisted budget allocation toward a savings goal. Reuses recommend.py's
spending_profile() for real per-category history; the LLM proposes how to
split a required monthly cut across categories and why, but the code - never
the model - guarantees the numbers actually add up to the target. Matches the
same rules-first split used everywhere else in this app: deterministic math
decides the number that must be trusted, the LLM only reasons/phrases."""

from __future__ import annotations

from typing import Optional

import anthropic
from pydantic import BaseModel

from app import llm_cache
from app.llm_metrics import log_usage

MODEL = "claude-sonnet-5"
FEATURE = "auto_budget"

# Never propose cutting a category's budget below this fraction of its real
# average spend, even in the fallback path - a "suggestion" that starves a
# category isn't useful, it's just a number nobody will actually follow.
MIN_BUDGET_FRACTION = 0.5

_DISCRETIONARY_PRIORITY = ["Entertainment", "Subscriptions", "Other", "Food", "Transport", "Housing"]

SYSTEM_PROMPT = (
    "A user wants to free up a specific amount more per month toward a savings "
    "goal. Given their real average monthly spend per category, propose a new "
    "monthly budget for each category such that the total reduction from "
    "current average spend is at least the amount needed. Prefer cutting "
    "discretionary categories first (Entertainment, Subscriptions, Other, "
    "Food) before fixed ones (Housing, Transport). Never propose a budget "
    "below half a category's average spend. One short, concrete rationale per "
    "category referencing the actual numbers - never invent a spend figure. "
    "If reference facts are given for Housing (local rent, mortgage rates), "
    "use them only in the Housing rationale."
)


class CategoryBudgetSuggestion(BaseModel):
    category: str
    suggested_budget: float
    rationale: str


class AutoBudgetSuggestions(BaseModel):
    suggestions: list[CategoryBudgetSuggestion]
    summary: str


_client: Optional[anthropic.Anthropic] = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        # See app.recommend._get_client - same reasoning for a short timeout.
        _client = anthropic.Anthropic(timeout=20.0)
    return _client


def _build_user_message(
    goal_name: str, required_cut: float, profile: dict, current_budgets: dict, housing_facts: Optional[list[dict]]
) -> str:
    lines = [
        f"Goal: {goal_name}. Needs ${required_cut:.2f}/mo more in savings capacity than "
        "current budgets provide.",
        "\nSpending history by category (months with $0 spend excluded):",
    ]
    for category, stats in profile.items():
        current = current_budgets.get(category)
        budget_note = f", current budget ${current}" if current is not None else ", no budget set yet"
        lines.append(
            f"- {category}: average ${stats['average']}/mo over {stats['months_observed']} month(s), "
            f"range ${stats['min']}-${stats['max']}, most recent month ${stats['most_recent']}{budget_note}"
        )
    if housing_facts:
        lines.append("\nReference facts for Housing (use only in the Housing rationale):")
        lines.extend(f"- {f['text']}" for f in housing_facts)
    lines.append(f"\nPropose a new monthly budget per category above that collectively frees up at least ${required_cut:.2f}/mo.")
    return "\n".join(lines)


def _rescale_to_meet_target(suggestions: list[dict], profile: dict, required_cut: float) -> list[dict]:
    """The LLM is asked to make its proposed cuts sum to required_cut and never
    cut below half a category's average, but LLMs are unreliable at exact
    arithmetic - this is the code-level guardrail, not a trust-the-model step.

    The floor (never below half of average) is enforced unconditionally on
    every suggestion. On top of that: if the model's total cut already meets
    or exceeds required_cut, its allocation is otherwise left alone - extra
    headroom isn't a problem. If it falls short, every cut is scaled up by
    the same factor so the total lands exactly on required_cut. The model
    chooses allocation and rationale; this guarantees the number."""
    floored = []
    cuts = []
    for s in suggestions:
        avg = profile.get(s["category"], {}).get("average", s["suggested_budget"])
        floor = avg * MIN_BUDGET_FRACTION
        budget = max(s["suggested_budget"], floor)
        floored.append({**s, "suggested_budget": round(budget, 2)})
        cuts.append(max(avg - budget, 0.0))
    total_cut = sum(cuts)

    if required_cut <= 0 or total_cut <= 0 or total_cut >= required_cut:
        return floored

    scale = required_cut / total_cut
    rescaled = []
    for s, cut in zip(floored, cuts):
        avg = profile.get(s["category"], {}).get("average", s["suggested_budget"])
        floor = avg * MIN_BUDGET_FRACTION
        new_budget = max(avg - cut * scale, floor)
        rescaled.append({**s, "suggested_budget": round(new_budget, 2)})
    return rescaled


def _fallback_suggestions(profile: dict, required_cut: float) -> dict:
    """Used only if the Anthropic call fails - cuts discretionary categories
    first, never below half their average spend, until the target is met, so
    an LLM outage never blocks getting *some* suggestion."""
    ordered = sorted(
        profile.items(),
        key=lambda kv: _DISCRETIONARY_PRIORITY.index(kv[0]) if kv[0] in _DISCRETIONARY_PRIORITY else len(_DISCRETIONARY_PRIORITY),
    )
    remaining = required_cut
    suggestions = []
    for category, stats in ordered:
        if remaining <= 0:
            break
        max_cut = stats["average"] * (1 - MIN_BUDGET_FRACTION)
        cut = min(max_cut, remaining)
        if cut <= 0:
            continue
        remaining -= cut
        suggestions.append(
            {
                "category": category,
                "suggested_budget": round(stats["average"] - cut, 2),
                "rationale": f"Cutting ${cut:.2f}/mo from this category's ${stats['average']}/mo average.",
            }
        )
    return {
        "suggestions": suggestions,
        "summary": f"Proposed cuts to free up ${required_cut:.2f}/mo toward your goal.",
    }


def recommend_budget_for_goal(
    goal_name: str,
    required_cut: float,
    profile: dict,
    current_budgets: dict,
    housing_facts: Optional[list[dict]] = None,
) -> dict:
    if required_cut <= 0:
        return {"suggestions": [], "summary": "You're already on pace for this goal.", "source": "not_needed", "error": None}
    if not profile:
        return {
            "suggestions": [],
            "summary": "Not enough spending history yet to suggest budget cuts.",
            "source": "none",
            "error": None,
        }

    key = llm_cache.cache_key(FEATURE, goal_name, required_cut, profile, current_budgets, housing_facts)
    cached = llm_cache.get(key)
    if cached is not None:
        log_usage(FEATURE, MODEL, input_tokens=0, output_tokens=0, cached=True)
        return cached

    try:
        response = _get_client().messages.parse(
            model=MODEL,
            # Higher than recommend.py's 800 - one suggestion per budgeted
            # category plus a rationale each, which truncates mid-JSON well
            # before 800 tokens once there are 4+ categories.
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": _build_user_message(goal_name, required_cut, profile, current_budgets, housing_facts)}
            ],
            output_format=AutoBudgetSuggestions,
        )
        parsed = response.parsed_output
        log_usage(FEATURE, MODEL, response.usage.input_tokens, response.usage.output_tokens)
        rescaled = _rescale_to_meet_target([s.model_dump() for s in parsed.suggestions], profile, required_cut)
        result = {"suggestions": rescaled, "summary": parsed.summary, "source": "ai", "error": None}
        llm_cache.set(key, result)
        return result
    except Exception as exc:
        result = _fallback_suggestions(profile, required_cut)
        result["source"] = "fallback"
        result["error"] = str(exc)
        return result
