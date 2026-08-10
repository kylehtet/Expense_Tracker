# LLM Cost Benchmark

Real Anthropic API calls, 18 fixed scenarios (12 affordability checks + 6 budget recommendations) built from the 30-transaction Sandbox fixture (`tests/fixtures/sandbox_transactions.json`). Every number below is a real `usage.input_tokens` / `usage.output_tokens` from an actual API response - both versions use the same model (`claude-sonnet-5`), so the only variable is what's in the prompt.

**Naive** reconstructs what an unoptimized first pass would send: the full raw transaction list plus budgets, asking the model to do the arithmetic itself and explain the result in one shot.

**Refactored** is the actual code path in `app/explain.py` / `app/recommend.py`: the rules engine (`app/affordability.py`, `app/budget.py`) computes the verdict/stats first, and the model only receives those already-computed facts to phrase or reason over.

## Results

| | Naive | Refactored | Change |
|---|---|---|---|
| Input tokens | 65,878 | 8,276 | -57,602 |
| Output tokens | 9,445 | 3,914 | -5,531 |
| **Total tokens** | **75,323** | **12,190** | **-83.8%** |
| Cost for these 18 scenarios | $0.2262 | $0.0557 | -75.4% |
| Cost per 1,000 requests (same mix) | $12.57 | $3.09 | -$9.47 |

Pricing: Claude Sonnet 5, $2.00 / $10.00 per million input/output tokens (Anthropic's published rate, introductory through 2026-08-31, checked 2026-08-09).

Caching (`app/llm_cache.py`) is not reflected in these totals - every scenario here has a unique input by design, so the cache never fires. In production, repeated identical requests (e.g. re-checking the same purchase) cost zero additional tokens on top of these numbers.

## Per-scenario detail

| # | Feature | Naive tokens | Refactored tokens |
|---|---|---|---|
| 1 | explain_verdict | 3,853 | 383 |
| 2 | explain_verdict | 3,900 | 378 |
| 3 | explain_verdict | 4,023 | 377 |
| 4 | explain_verdict | 3,827 | 369 |
| 5 | explain_verdict | 3,827 | 366 |
| 6 | explain_verdict | 3,953 | 333 |
| 7 | explain_verdict | 4,003 | 371 |
| 8 | explain_verdict | 4,456 | 370 |
| 9 | explain_verdict | 3,900 | 372 |
| 10 | explain_verdict | 3,866 | 361 |
| 11 | explain_verdict | 3,996 | 375 |
| 12 | explain_verdict | 3,965 | 354 |
| 13 | recommend_budgets | 4,616 | 1,120 |
| 14 | recommend_budgets | 4,626 | 1,154 |
| 15 | recommend_budgets | 4,616 | 1,289 |
| 16 | recommend_budgets | 4,635 | 1,513 |
| 17 | recommend_budgets | 4,616 | 1,299 |
| 18 | recommend_budgets | 4,645 | 1,406 |
