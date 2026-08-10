"""Benchmarks real Anthropic token usage: a reconstructed "naive" single-shot
call (raw transactions dumped into the prompt, LLM does the math itself) vs.
the actual refactored call this app makes today (deterministic rules-engine
output only, LLM only phrases/reasons over already-computed facts).

Makes real API calls against ANTHROPIC_API_KEY - this costs a small, real
amount of money to run (roughly a few cents at current pricing). Every number
in benchmark_results.md comes from an actual `usage.input_tokens` /
`usage.output_tokens` on a real response, not an estimate.

Run with: .venv/bin/python benchmark_llm_cost.py
"""

from __future__ import annotations

import json
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv

load_dotenv()

from app.affordability import check_purchase
from app.budget import budget_status
from app.categorize import categorize_transaction
from app.explain import MODEL as EXPLAIN_MODEL
from app.explain import SYSTEM_PROMPT as EXPLAIN_SYSTEM_PROMPT
from app.explain import _build_user_message as build_explain_message
from app.explain import _get_client as get_explain_client
from app.recommend import MODEL as RECOMMEND_MODEL
from app.recommend import SYSTEM_PROMPT as RECOMMEND_SYSTEM_PROMPT
from app.recommend import BudgetRecommendations
from app.recommend import _build_user_message as build_recommend_message
from app.recommend import _get_client as get_recommend_client
from app.recommend import spending_profile

FIXTURES_PATH = Path(__file__).resolve().parent / "tests" / "fixtures" / "sandbox_transactions.json"
RESULTS_PATH = Path(__file__).resolve().parent / "benchmark_results.md"

# Looked up 2026-08-09 (Anthropic's published API pricing). Sonnet 5's rate is
# introductory pricing valid through 2026-08-31.
PRICING_PER_MTOK = {
    "claude-sonnet-5": {"input": 2.00, "output": 10.00},
}

TODAY = date(2026, 7, 20)  # falls in the fixture's most recent month (July)

NAIVE_EXPLAIN_SYSTEM = (
    "You are a personal finance assistant. Given a user's raw bank transactions "
    "and their monthly budgets, figure out whether they can afford a new "
    "purchase: work out how much of each relevant budget is left, decide "
    "whether the purchase fits, and explain your reasoning in 1-3 sentences."
)

NAIVE_RECOMMEND_SYSTEM = (
    "You are a personal finance assistant. Given a user's raw bank "
    "transactions, work out their typical monthly spend per category and "
    "recommend a sensible monthly budget for each one, with a short "
    "rationale for each recommendation."
)

# Generous, un-tuned caps - representative of a first-pass implementation
# that hasn't been sized to the actual output, which is exactly what Step 3
# of this refactor fixed on the real call sites.
NAIVE_EXPLAIN_MAX_TOKENS = 1024
NAIVE_RECOMMEND_MAX_TOKENS = 1024


def _load_categorized_transactions() -> list[dict]:
    with open(FIXTURES_PATH) as f:
        raw = json.load(f)
    for t in raw:
        t["category"] = categorize_transaction(t)
    return raw


def _actual_spend_for_month(transactions: list[dict], month: str) -> dict[str, float]:
    spend: dict[str, float] = {}
    for t in transactions:
        if t["date"].startswith(month):
            spend[t["category"]] = spend.get(t["category"], 0.0) + t["amount"]
    return {c: round(v, 2) for c, v in spend.items()}


def naive_explain_prompt(transactions: list[dict], budgets: dict, price: float, category: str, timing: str) -> str:
    return (
        "Raw transactions this month (JSON):\n"
        f"{json.dumps(transactions)}\n\n"
        "Current monthly budgets by category (JSON):\n"
        f"{json.dumps(budgets)}\n\n"
        f"Question: Can I afford a ${price:.2f} {timing} purchase in the "
        f"'{category}' category? Explain in 1-3 sentences."
    )


def naive_recommend_prompt(transactions: list[dict], current_budgets: dict) -> str:
    return (
        "Raw transactions (JSON):\n"
        f"{json.dumps(transactions)}\n\n"
        "Current budgets by category (JSON):\n"
        f"{json.dumps(current_budgets)}\n\n"
        "Recommend a monthly budget for each spending category based on this "
        "history, with a short rationale for each one."
    )


# ---------------------------------------------------------------------------
# Scenarios - 12 affordability checks + 6 budget recommendations = 18 total,
# all built from the same real 30-transaction Sandbox fixture used by the
# test suite. Budgets below are a fixed, realistic monthly budget set.
# ---------------------------------------------------------------------------

BUDGETS = {"Housing": 1600.0, "Food": 300.0, "Transport": 550.0, "Subscriptions": 60.0, "Entertainment": 100.0}

EXPLAIN_SCENARIOS = [
    {"price": 50.0, "category": "Entertainment", "timing": "one_time"},
    {"price": 480.0, "category": "Entertainment", "timing": "one_time"},
    {"price": 20.0, "category": "Subscriptions", "timing": "monthly"},
    {"price": 50.0, "category": "Housing", "timing": "one_time"},
    {"price": 100.0, "category": "Food", "timing": "one_time"},
    {"price": 200.0, "category": "Food", "timing": "split_3"},
    {"price": 300.0, "category": "Transport", "timing": "one_time"},
    {"price": 200.0, "category": "Other", "timing": "one_time"},
    {"price": 1000.0, "category": "Entertainment", "timing": "monthly"},
    {"price": 2000.0, "category": "Housing", "timing": "one_time"},
    {"price": 5.0, "category": "Subscriptions", "timing": "one_time"},
    {"price": 700.0, "category": "Transport", "timing": "one_time"},
]

RECOMMEND_SCENARIOS = [
    {"months": 1, "current_budgets": {}},
    {"months": 1, "current_budgets": {"Housing": 1600.0}},
    {"months": 2, "current_budgets": {}},
    {"months": 2, "current_budgets": {"Housing": 1600.0, "Food": 300.0}},
    {"months": 3, "current_budgets": {}},
    {"months": 3, "current_budgets": {"Housing": 1600.0, "Food": 300.0, "Transport": 550.0}},
]


def run_explain_scenario(transactions: list[dict], scenario: dict) -> dict:
    actual_spend = _actual_spend_for_month(transactions, "2026-07")
    status = budget_status(BUDGETS, actual_spend)
    facts = check_purchase(status, scenario["price"], scenario["category"], scenario["timing"], today=TODAY)

    naive_response = get_explain_client().messages.create(
        model=EXPLAIN_MODEL,
        max_tokens=NAIVE_EXPLAIN_MAX_TOKENS,
        system=NAIVE_EXPLAIN_SYSTEM,
        messages=[{"role": "user", "content": naive_explain_prompt(transactions, BUDGETS, **scenario)}],
    )
    refactored_response = get_explain_client().messages.create(
        model=EXPLAIN_MODEL,
        max_tokens=150,
        system=EXPLAIN_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_explain_message(facts)}],
    )
    return {
        "feature": "explain_verdict",
        "naive_input": naive_response.usage.input_tokens,
        "naive_output": naive_response.usage.output_tokens,
        "refactored_input": refactored_response.usage.input_tokens,
        "refactored_output": refactored_response.usage.output_tokens,
    }


def run_recommend_scenario(transactions: list[dict], scenario: dict) -> dict:
    profile = spending_profile(transactions, months=scenario["months"])

    naive_response = get_recommend_client().messages.create(
        model=RECOMMEND_MODEL,
        max_tokens=NAIVE_RECOMMEND_MAX_TOKENS,
        system=NAIVE_RECOMMEND_SYSTEM,
        messages=[{"role": "user", "content": naive_recommend_prompt(transactions, scenario["current_budgets"])}],
    )
    refactored_response = get_recommend_client().messages.parse(
        model=RECOMMEND_MODEL,
        max_tokens=800,
        system=RECOMMEND_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_recommend_message(profile, scenario["current_budgets"])}],
        output_format=BudgetRecommendations,
    )
    return {
        "feature": "recommend_budgets",
        "naive_input": naive_response.usage.input_tokens,
        "naive_output": naive_response.usage.output_tokens,
        "refactored_input": refactored_response.usage.input_tokens,
        "refactored_output": refactored_response.usage.output_tokens,
    }


def main() -> None:
    transactions = _load_categorized_transactions()
    results = []

    total = len(EXPLAIN_SCENARIOS) + len(RECOMMEND_SCENARIOS)
    done = 0

    for scenario in EXPLAIN_SCENARIOS:
        done += 1
        print(f"[{done}/{total}] explain_verdict  {scenario}", file=sys.stderr)
        try:
            results.append(run_explain_scenario(transactions, scenario))
        except Exception as exc:
            print(f"  SKIPPED (error: {exc})", file=sys.stderr)
        time.sleep(0.2)

    for scenario in RECOMMEND_SCENARIOS:
        done += 1
        print(f"[{done}/{total}] recommend_budgets  {scenario}", file=sys.stderr)
        try:
            results.append(run_recommend_scenario(transactions, scenario))
        except Exception as exc:
            print(f"  SKIPPED (error: {exc})", file=sys.stderr)
        time.sleep(0.2)

    naive_input = sum(r["naive_input"] for r in results)
    naive_output = sum(r["naive_output"] for r in results)
    refactored_input = sum(r["refactored_input"] for r in results)
    refactored_output = sum(r["refactored_output"] for r in results)

    naive_total = naive_input + naive_output
    refactored_total = refactored_input + refactored_output
    reduction_pct = round((1 - refactored_total / naive_total) * 100, 1)

    price = PRICING_PER_MTOK["claude-sonnet-5"]
    naive_cost = naive_input / 1_000_000 * price["input"] + naive_output / 1_000_000 * price["output"]
    refactored_cost = refactored_input / 1_000_000 * price["input"] + refactored_output / 1_000_000 * price["output"]
    cost_reduction_pct = round((1 - refactored_cost / naive_cost) * 100, 1)

    n = len(results)
    naive_cost_per_1000 = naive_cost / n * 1000
    refactored_cost_per_1000 = refactored_cost / n * 1000

    lines = [
        "# LLM Cost Benchmark",
        "",
        f"Real Anthropic API calls, {n} fixed scenarios (12 affordability checks + "
        "6 budget recommendations) built from the 30-transaction Sandbox fixture "
        "(`tests/fixtures/sandbox_transactions.json`). Every number below is a "
        "real `usage.input_tokens` / `usage.output_tokens` from an actual API "
        "response - both versions use the same model (`claude-sonnet-5`), so "
        "the only variable is what's in the prompt.",
        "",
        "**Naive** reconstructs what an unoptimized first pass would send: the "
        "full raw transaction list plus budgets, asking the model to do the "
        "arithmetic itself and explain the result in one shot.",
        "",
        "**Refactored** is the actual code path in `app/explain.py` / "
        "`app/recommend.py`: the rules engine (`app/affordability.py`, "
        "`app/budget.py`) computes the verdict/stats first, and the model "
        "only receives those already-computed facts to phrase or reason "
        "over.",
        "",
        "## Results",
        "",
        "| | Naive | Refactored | Change |",
        "|---|---|---|---|",
        f"| Input tokens | {naive_input:,} | {refactored_input:,} | -{naive_input - refactored_input:,} |",
        f"| Output tokens | {naive_output:,} | {refactored_output:,} | -{naive_output - refactored_output:,} |",
        f"| **Total tokens** | **{naive_total:,}** | **{refactored_total:,}** | **-{reduction_pct}%** |",
        f"| Cost for these {n} scenarios | ${naive_cost:.4f} | ${refactored_cost:.4f} | -{cost_reduction_pct}% |",
        f"| Cost per 1,000 requests (same mix) | ${naive_cost_per_1000:.2f} | ${refactored_cost_per_1000:.2f} | "
        f"-${naive_cost_per_1000 - refactored_cost_per_1000:.2f} |",
        "",
        f"Pricing: Claude Sonnet 5, ${price['input']:.2f} / ${price['output']:.2f} per "
        "million input/output tokens (Anthropic's published rate, introductory "
        "through 2026-08-31, checked 2026-08-09).",
        "",
        "Caching (`app/llm_cache.py`) is not reflected in these totals - every "
        "scenario here has a unique input by design, so the cache never fires. "
        "In production, repeated identical requests (e.g. re-checking the same "
        "purchase) cost zero additional tokens on top of these numbers.",
        "",
        "## Per-scenario detail",
        "",
        "| # | Feature | Naive tokens | Refactored tokens |",
        "|---|---|---|---|",
    ]
    for i, r in enumerate(results, start=1):
        lines.append(
            f"| {i} | {r['feature']} | {r['naive_input'] + r['naive_output']:,} | "
            f"{r['refactored_input'] + r['refactored_output']:,} |"
        )

    RESULTS_PATH.write_text("\n".join(lines) + "\n")
    print(f"\nWrote {RESULTS_PATH}", file=sys.stderr)
    print(f"Total tokens: {naive_total:,} -> {refactored_total:,} ({reduction_pct}% reduction)", file=sys.stderr)


if __name__ == "__main__":
    main()
