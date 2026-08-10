"""Head-to-head: Sonnet 5 vs Haiku 4.5 on the exact same refactored prompts
this app sends today (app/explain.py, app/recommend.py) - same 18 fixed
scenarios as benchmark_llm_cost.py. Real API calls on both models, real
token counts, plus the actual generated text side by side so quality can be
judged directly instead of guessed at.

Run with: .venv/bin/python benchmark_model_comparison.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv

load_dotenv()

from app.affordability import check_purchase
from app.budget import budget_status
from app.explain import SYSTEM_PROMPT as EXPLAIN_SYSTEM_PROMPT
from app.explain import _build_user_message as build_explain_message
from app.explain import _get_client as get_explain_client
from app.recommend import SYSTEM_PROMPT as RECOMMEND_SYSTEM_PROMPT
from app.recommend import BudgetRecommendations
from app.recommend import _build_user_message as build_recommend_message
from app.recommend import _get_client as get_recommend_client
from app.recommend import spending_profile

from benchmark_llm_cost import (
    BUDGETS,
    EXPLAIN_SCENARIOS,
    RECOMMEND_SCENARIOS,
    TODAY,
    _actual_spend_for_month,
    _load_categorized_transactions,
)

RESULTS_PATH = Path(__file__).resolve().parent / "benchmark_model_comparison.md"

MODELS = ["claude-sonnet-5", "claude-haiku-4-5"]

# Looked up 2026-08-09 (Anthropic's published API pricing). Sonnet 5's rate is
# introductory pricing valid through 2026-08-31.
PRICING_PER_MTOK = {
    "claude-sonnet-5": {"input": 2.00, "output": 10.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
}

# A handful of scenarios, printed in full for both models so quality can be
# read directly rather than inferred from token counts alone.
SAMPLE_EXPLAIN_INDICES = {0, 1, 8, 9}  # comfortable, tight, over(monthly), over(one_time)
SAMPLE_RECOMMEND_INDICES = {0, 5}  # 1-month/no-budgets, 3-month/full-budgets


def run_explain(model: str, facts: dict) -> dict:
    response = get_explain_client().messages.create(
        model=model,
        max_tokens=150,
        system=EXPLAIN_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_explain_message(facts)}],
    )
    text = next((b.text for b in response.content if b.type == "text"), "").strip()
    return {"text": text, "input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens}


def run_recommend(model: str, profile: dict, current_budgets: dict) -> dict:
    response = get_recommend_client().messages.parse(
        model=model,
        max_tokens=800,
        system=RECOMMEND_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_recommend_message(profile, current_budgets)}],
        output_format=BudgetRecommendations,
    )
    parsed = response.parsed_output
    text = parsed.summary + "\n" + "\n".join(f"- {r.category}: ${r.recommended_budget} - {r.rationale}" for r in parsed.recommendations)
    return {"text": text, "input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens}


def main() -> None:
    transactions = _load_categorized_transactions()
    actual_spend = _actual_spend_for_month(transactions, "2026-07")
    status = budget_status(BUDGETS, actual_spend)

    totals = {m: {"input": 0, "output": 0, "n": 0} for m in MODELS}
    samples = []

    total_calls = (len(EXPLAIN_SCENARIOS) + len(RECOMMEND_SCENARIOS)) * len(MODELS)
    done = 0

    for i, scenario in enumerate(EXPLAIN_SCENARIOS):
        facts = check_purchase(status, scenario["price"], scenario["category"], scenario["timing"], today=TODAY)
        row = {"feature": "explain_verdict", "scenario": scenario, "by_model": {}}
        for model in MODELS:
            done += 1
            print(f"[{done}/{total_calls}] explain_verdict  {model}  {scenario}", file=sys.stderr)
            try:
                result = run_explain(model, facts)
            except Exception as exc:
                print(f"  SKIPPED (error: {exc})", file=sys.stderr)
                continue
            totals[model]["input"] += result["input_tokens"]
            totals[model]["output"] += result["output_tokens"]
            totals[model]["n"] += 1
            row["by_model"][model] = result
        if i in SAMPLE_EXPLAIN_INDICES:
            samples.append(row)

    for i, scenario in enumerate(RECOMMEND_SCENARIOS):
        profile = spending_profile(transactions, months=scenario["months"])
        row = {"feature": "recommend_budgets", "scenario": scenario, "by_model": {}}
        for model in MODELS:
            done += 1
            print(f"[{done}/{total_calls}] recommend_budgets  {model}  {scenario}", file=sys.stderr)
            try:
                result = run_recommend(model, profile, scenario["current_budgets"])
            except Exception as exc:
                print(f"  SKIPPED (error: {exc})", file=sys.stderr)
                continue
            totals[model]["input"] += result["input_tokens"]
            totals[model]["output"] += result["output_tokens"]
            totals[model]["n"] += 1
            row["by_model"][model] = result
        if i in SAMPLE_RECOMMEND_INDICES:
            samples.append(row)

    lines = [
        "# Model Comparison: Sonnet 5 vs Haiku 4.5",
        "",
        "Same 18 scenarios and same refactored prompts as `benchmark_results.md`, "
        "run on both models. Real `usage.input_tokens` / `usage.output_tokens` "
        "and real generated text from both - not estimated.",
        "",
        "## Token & cost totals",
        "",
        "| Model | Calls | Input tokens | Output tokens | Cost for 18 scenarios | Cost per 1,000 requests |",
        "|---|---|---|---|---|---|",
    ]
    for model in MODELS:
        t = totals[model]
        price = PRICING_PER_MTOK[model]
        cost = t["input"] / 1_000_000 * price["input"] + t["output"] / 1_000_000 * price["output"]
        cost_per_1000 = cost / t["n"] * 1000 if t["n"] else 0.0
        lines.append(
            f"| {model} | {t['n']} | {t['input']:,} | {t['output']:,} | ${cost:.4f} | ${cost_per_1000:.2f} |"
        )

    sonnet_cost = totals["claude-sonnet-5"]
    haiku_cost = totals["claude-haiku-4-5"]
    if sonnet_cost["n"] and haiku_cost["n"]:
        s_price, h_price = PRICING_PER_MTOK["claude-sonnet-5"], PRICING_PER_MTOK["claude-haiku-4-5"]
        s_total_cost = sonnet_cost["input"] / 1e6 * s_price["input"] + sonnet_cost["output"] / 1e6 * s_price["output"]
        h_total_cost = haiku_cost["input"] / 1e6 * h_price["input"] + haiku_cost["output"] / 1e6 * h_price["output"]
        pct = round((1 - h_total_cost / s_total_cost) * 100, 1)
        lines.append("")
        lines.append(f"Switching model alone (same prompts, already-refactored): **-{pct}% cost**, on top of the 83.8% already banked by the prompt refactor.")

    lines += [
        "",
        "Pricing checked 2026-08-09: Sonnet 5 $2.00/$10.00 per MTok (introductory, "
        "through 2026-08-31), Haiku 4.5 $1.00/$5.00 per MTok.",
        "",
        "## Sample outputs, side by side",
        "",
        "Judge quality yourself - these are the actual model responses, unedited.",
        "",
    ]
    for row in samples:
        lines.append(f"### {row['feature']} — {row['scenario']}")
        lines.append("")
        for model in MODELS:
            result = row["by_model"].get(model)
            if result is None:
                continue
            lines.append(f"**{model}** ({result['input_tokens']}in/{result['output_tokens']}out tokens):")
            lines.append("")
            lines.append("> " + result["text"].replace("\n", "\n> "))
            lines.append("")

    RESULTS_PATH.write_text("\n".join(lines) + "\n")
    print(f"\nWrote {RESULTS_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()
