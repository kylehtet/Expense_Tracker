# Model Comparison: Sonnet 5 vs Haiku 4.5

Same 18 scenarios and same refactored prompts as `benchmark_results.md`, run on both models. Real `usage.input_tokens` / `usage.output_tokens` and real generated text from both - not estimated.

## Token & cost totals

| Model | Calls | Input tokens | Output tokens | Cost for 18 scenarios | Cost per 1,000 requests |
|---|---|---|---|---|---|
| claude-sonnet-5 | 18 | 8,276 | 4,235 | $0.0589 | $3.27 |
| claude-haiku-4-5 | 18 | 6,536 | 2,787 | $0.0205 | $1.14 |

Switching model alone (same prompts, already-refactored): **-65.2% cost**, on top of the 83.8% already banked by the prompt refactor.

Pricing checked 2026-08-09: Sonnet 5 $2.00/$10.00 per MTok (introductory, through 2026-08-31), Haiku 4.5 $1.00/$5.00 per MTok.

## Sample outputs, side by side

Judge quality yourself - these are the actual model responses, unedited.

### explain_verdict — {'price': 50.0, 'category': 'Entertainment', 'timing': 'one_time'}

**claude-sonnet-5** (264in/116out tokens):

> This $50.00 one-time purchase fits comfortably in your Entertainment budget, leaving $22.00 there (down from $72.0) and $902.07 across all budgets (down from $952.07). With 12 days left in the month, that keeps you at $79.34 safe to spend per day, or you could split the cost into $16.67/mo over 3 months.

**claude-haiku-4-5** (195in/83out tokens):

> You have $72.00 available in Entertainment and this $50.00 purchase leaves you with $22.00 in that category, which fits comfortably within your current budget. Across all your budgets, you'll have $902.07 remaining after this purchase, giving you $79.34 per day to spend safely over the next 12 days.

### explain_verdict — {'price': 480.0, 'category': 'Entertainment', 'timing': 'one_time'}

**claude-sonnet-5** (267in/117out tokens):

> This $480.00 purchase would take your Entertainment budget from $72.0 left to -408.0, but across all your budgets combined, you'd still have $472.07 left, dropping your safe daily spending to $79.34 over the remaining 12 days. Splitting it into 3 monthly payments of $160.00 would avoid pushing Entertainment negative.

**claude-haiku-4-5** (197in/103out tokens):

> This $480.00 entertainment purchase would leave your Entertainment budget at -$408.00, putting it $408.00 over limit, though your overall budgets would still have $472.07 remaining across all categories for the next 12 days. You'd have $79.34 available per day to spend safely for the rest of the month after this purchase, or you could spread the cost to $160.00 per month over 3 months instead.

### explain_verdict — {'price': 1000.0, 'category': 'Entertainment', 'timing': 'monthly'}

**claude-sonnet-5** (265in/126out tokens):

> This $1000.00 monthly Entertainment purchase doesn't fit: your Entertainment budget only has $72.0 left, so this would leave you at -$928.0 there, and your overall budget would go from $952.07 to -$47.93. With 12 days left in the month and $79.34 safe to spend per day, splitting this into 3 months would bring it down to $333.33/mo.

**claude-haiku-4-5** (193in/112out tokens):

> A $1,000.00 monthly Entertainment purchase doesn't fit your current budget because you only have $72.00 remaining in that category, which would leave you at -$928.00 and push your overall budget to -$47.93 with 12 days left in the month. You can safely spend $79.34 per day for the remaining 12 days across all categories, or spread this purchase across 3 months at $333.33 per month to fit within your budget.

### explain_verdict — {'price': 2000.0, 'category': 'Housing', 'timing': 'one_time'}

**claude-sonnet-5** (261in/104out tokens):

> This $2000.00 one-time purchase in Housing doesn't fit: your Housing budget only has $100.0 left, so this would leave it at -$1900.0, and your overall budget would go from $952.07 to -$1047.93. Spreading the cost over 3 months would bring it to $666.67/mo instead.

**claude-haiku-4-5** (197in/105out tokens):

> You have $100.00 left in your Housing budget, but this purchase costs $2000.00, creating a shortfall of $1900.00 in that category. Across all your budgets, you would have -$1047.93 remaining if you make this purchase, meaning you'd overspend your total monthly budget by that amount. Spreading this cost to $666.67 per month over 3 months would keep you within your current budget limits.

### recommend_budgets — {'months': 1, 'current_budgets': {}}

**claude-sonnet-5** (826in/302out tokens):

> With only one month of data per category, budgets are set close to the actual spend, rounded to the nearest $5-$10, with small upward nudges for variable categories like Entertainment and Food to provide buffer.
> - Entertainment: $30.0 - Only one month on record at $28.0; rounded up slightly to $30 to give a little cushion.
> - Food: $155.0 - Single month spend of $150.95; rounded up to $155 to allow small variability.
> - Housing: $1500.0 - Only data point is $1500.0, a fixed cost, so budget set to match exactly.
> - Subscriptions: $70.0 - One month recorded at $70.48; rounded to nearest $10 for a clean budget of $70.

**claude-haiku-4-5** (669in/233out tokens):

> Recommended monthly budgets total $1,755 based on your recent spending patterns: Housing ($1,500), Food ($155), Subscriptions ($70), and Entertainment ($30).
> - Entertainment: $30.0 - Single month of $28.0 spend; rounding up slightly to $30 provides modest buffer for occasional entertainment expenses.
> - Food: $155.0 - Average spend of $150.95 over the month; rounding to $155 allows for minor fluctuations in grocery and dining costs.
> - Housing: $1500.0 - Consistent fixed expense of $1500.0; maintaining this level matches demonstrated housing costs.
> - Subscriptions: $70.0 - Stable monthly spend of $70.48; rounding to $70 reflects predictable subscription commitments.

### recommend_budgets — {'months': 3, 'current_budgets': {'Housing': 1600.0, 'Food': 300.0, 'Transport': 550.0}}

**claude-sonnet-5** (878in/511out tokens):

> Recommendations are based on 2-3 months of actual spend per category, rounded to nearest $5-$10, nudged upward where recent months show increases or volatility (Subscriptions, Transport, Entertainment). Food and Housing budgets are set near their stable averages, both notably lower than current allotments.
> - Entertainment: $45.0 - Average $40.0/mo with range $28.0-$59.99; rounded up slightly to $45 to cover volatility despite recent dip to $28.0.
> - Food: $155.0 - Consistent spend averaging $152.92/mo (range $147.7-$160.1); $155 covers typical months, well under current $300 budget.
> - Housing: $1585.0 - Average $1585.0/mo over 3 months (range $1500.0-$1635.0); set at average since recent month dropped to $1500.0, close to current $1600.0 budget.
> - Subscriptions: $70.0 - Average $41.15/mo but most recent month jumped to $70.48 (range $26.48-$70.48); budget at $70 to match rising trend.
> - Transport: $80.0 - Average $72.58/mo over 2 months with most recent at $78.0 (range $67.15-$78.0); rounded up to $80 to reflect upward trend, far below current $550.0 budget.

**claude-haiku-4-5** (718in/348out tokens):

> Adjusted budgets align actual spending patterns: reduce Food and Transport from excessive allocations, set Entertainment and Subscriptions based on average with volatility buffers, and maintain Housing at current level. Total recommended monthly budget: $1,930.
> - Entertainment: $45.0 - Average of $40/mo with recent spend at $28/mo; recommend $45 to accommodate occasional higher months (peak $59.99) while staying conservative.
> - Food: $155.0 - Consistent spending $147.7–$160.1/mo averaging $152.92; reduce current $300 budget to $155 to match actual consumption.
> - Housing: $1600.0 - Stable $1500–$1635/mo range averaging $1585; maintain current $1600 budget as it aligns well with historical spend.
> - Subscriptions: $50.0 - Average $41.15/mo but volatile ($26.48–$70.48) with recent spike to $70.48; recommend $50 to buffer against recurring high months.
> - Transport: $80.0 - Average $72.58/mo over 2 months with rising trend ($67.15→$78.0); recommend $80 to match recent spend and account for upward trajectory.

