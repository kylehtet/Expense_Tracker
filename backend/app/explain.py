"""Turns a deterministic affordability verdict (app.affordability.check_purchase)
into a short plain-language explanation. The verdict and every number are already
decided by rules.py-style arithmetic; this module's only job is phrasing - the
system prompt explicitly forbids inventing or adjusting any figure."""

from __future__ import annotations

import anthropic

from app import llm_cache
from app.llm_metrics import log_usage

MODEL = "claude-sonnet-5"
FEATURE = "explain_verdict"

SYSTEM_PROMPT = (
    "Write a 1-3 sentence, direct, concrete plain-language explanation of a "
    "personal finance affordability check, using only the exact pre-computed "
    "numbers given - never invent, round differently, or add a number. No "
    "financial advice or recommendations, and never use the word 'advice'."
)

VERDICT_LABEL = {
    "comfortable": "Fits comfortably",
    "tight": "Tight — it fits, barely",
    "over": "Doesn't fit",
}

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def _fact_line(label: str, value) -> str:
    return f"{label}: {'no budget set' if value is None else value}"


def _build_user_message(facts: dict) -> str:
    lines = [
        f"Purchase: ${facts['price']:.2f} ({facts['timing']}) in {facts['category']}.",
        f"Verdict: {VERDICT_LABEL.get(facts['verdict'], facts['verdict'])}",
        _fact_line(f"Left in {facts['category']} before this purchase", facts["category_left_before"]),
        _fact_line(f"Left in {facts['category']} after this purchase", facts["category_left_after"]),
        _fact_line("Left across all budgets before", facts["overall_left_before"]),
        _fact_line("Left across all budgets after", facts["overall_left_after"]),
        f"Days remaining in the month: {facts['days_remaining']}",
        f"Safe to spend per day for the rest of the month: ${facts['safe_to_spend_today']:.2f}",
    ]
    if facts["effect_on_pace_pct"] is not None:
        lines.append(f"Effect on daily spending pace: {facts['effect_on_pace_pct']:+.1f}%")
    if facts["timing"] != "split_3":
        lines.append(f"Split over 3 months instead would be: ${facts['split_monthly']:.2f}/mo")
    lines.append("\nWrite the 1-3 sentence explanation now.")
    return "\n".join(lines)


def _fallback_explanation(facts: dict) -> str:
    """Used only if the Anthropic call itself fails - a plain restatement of the
    verdict, so a synthesis outage never blocks the deterministic answer."""
    if facts["category_left_after"] is None:
        return (
            f"There's no budget set for {facts['category']}, so this is judged on your "
            f"overall budget only, which would have ${facts['overall_left_after']:.2f} left."
        )
    if facts["verdict"] == "comfortable":
        return (
            f"This fits within {facts['category']}, leaving ${facts['category_left_after']:.2f} "
            f"in that category and ${facts['overall_left_after']:.2f} across your overall budget."
        )
    if facts["verdict"] == "tight":
        return (
            f"This pushes {facts['category']} ${abs(facts['category_left_after']):.2f} over budget, "
            f"but your overall budget would still have ${facts['overall_left_after']:.2f} left."
        )
    return (
        f"This pushes {facts['category']} ${abs(facts['category_left_after']):.2f} over budget "
        f"and takes your overall budget ${abs(facts['overall_left_after']):.2f} negative."
    )


def explain_verdict(facts: dict) -> dict:
    key = llm_cache.cache_key(FEATURE, facts)
    cached = llm_cache.get(key)
    if cached is not None:
        log_usage(FEATURE, MODEL, input_tokens=0, output_tokens=0, cached=True)
        return cached

    try:
        response = _get_client().messages.create(
            model=MODEL,
            max_tokens=150,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _build_user_message(facts)}],
        )
        text = next((b.text for b in response.content if b.type == "text"), "").strip()
        if not text:
            raise ValueError("empty response")
        log_usage(FEATURE, MODEL, response.usage.input_tokens, response.usage.output_tokens)
        result = {"explanation": text, "source": "ai", "error": None}
        llm_cache.set(key, result)
        return result
    except Exception as exc:
        return {"explanation": _fallback_explanation(facts), "source": "fallback", "error": str(exc)}
