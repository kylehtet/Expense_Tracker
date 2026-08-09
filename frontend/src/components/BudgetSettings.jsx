import { useMemo, useState } from "react";
import { api } from "../api";
import { Corners } from "./Corners";

const CATEGORIES = ["Housing", "Food", "Transport", "Subscriptions", "Entertainment", "Other"];

const CATEGORY_VAR = {
  Housing: "var(--cat-housing)",
  Food: "var(--cat-food)",
  Entertainment: "var(--cat-entertainment)",
  Transport: "var(--cat-transport)",
  Other: "var(--cat-other)",
  Subscriptions: "var(--cat-subs)",
};

const currency = (value) => `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

// Average monthly spend per category, from whatever transaction history has
// already been fetched - not a live backend figure, an honest approximation
// from what's on hand. Months with no activity in a category count as $0.
function averageMonthlySpend(transactions) {
  const byCategoryMonth = {};
  const months = new Set();
  for (const t of transactions) {
    const month = t.date.slice(0, 7);
    months.add(month);
    byCategoryMonth[t.category] ??= {};
    byCategoryMonth[t.category][month] = (byCategoryMonth[t.category][month] ?? 0) + Math.max(t.amount, 0);
  }
  const monthCount = months.size || 1;
  const averages = {};
  for (const category of CATEGORIES) {
    const total = Object.values(byCategoryMonth[category] ?? {}).reduce((sum, v) => sum + v, 0);
    averages[category] = total / monthCount;
  }
  return averages;
}

export function BudgetSettings({ userId, status, transactions, onSaved }) {
  const [drafts, setDrafts] = useState({});
  const [saving, setSaving] = useState(false);
  const [recommendState, setRecommendState] = useState("idle"); // idle | loading | error
  const [recommendError, setRecommendError] = useState(null);
  const [recommendation, setRecommendation] = useState(null);

  const averages = useMemo(() => averageMonthlySpend(transactions), [transactions]);

  const valueFor = (category) => drafts[category] ?? status[category]?.budget ?? "";

  const hasHistory = transactions.length > 0;

  const autoFillFromAverages = () => {
    setDrafts((d) => {
      const next = { ...d };
      for (const category of CATEGORIES) {
        const avg = Math.round(averages[category] ?? 0);
        // A category with no spending history yet gets left empty (no limit)
        // rather than auto-set to $0, which would flag the first dollar spent
        // as over budget.
        next[category] = avg > 0 ? String(avg) : "";
      }
      return next;
    });
  };

  const getAiRecommendations = async () => {
    setRecommendState("loading");
    setRecommendError(null);
    try {
      const result = await api.recommendBudgets(userId, 6);
      setRecommendation(result);
      setRecommendState("idle");
    } catch (err) {
      setRecommendState("error");
      setRecommendError(err.status === 429 ? err.message : "Couldn't get recommendations. Try again.");
    }
  };

  const applyRecommendations = () => {
    if (!recommendation) return;
    setDrafts((d) => {
      const next = { ...d };
      for (const r of recommendation.recommendations) {
        next[r.category] = String(Math.round(r.recommended_budget));
      }
      return next;
    });
  };

  const totalBudgeted = CATEGORIES.reduce((sum, category) => {
    const v = Number(valueFor(category));
    return sum + (Number.isFinite(v) ? v : 0);
  }, 0);

  const saveAll = async () => {
    setSaving(true);
    try {
      for (const category of Object.keys(drafts)) {
        const amount = Number(drafts[category]);
        if (Number.isFinite(amount) && amount >= 0) {
          await api.setBudget(userId, category, amount);
        }
      }
      setDrafts({});
      onSaved();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="blueprint relative border border-hairline bg-ground">
      <Corners />
      <div className="px-[26px] py-[26px] pb-7">
        <h3 className="mb-1 font-display text-[16px] font-semibold uppercase tracking-[.07em] text-ink">
          Monthly budget by category
        </h3>
        <p className="mb-3 text-[13.5px] text-ink-muted">
          Six fixed categories. Leave a field empty to track spending without a limit.
        </p>
        {hasHistory && (
          <div className="mb-5 flex flex-wrap items-center gap-x-5 gap-y-2">
            <button
              type="button"
              onClick={autoFillFromAverages}
              className="font-display text-[12px] font-semibold uppercase tracking-[.06em] text-accent-deep hover:text-accent-press"
            >
              Auto-fill from average spend &rarr;
            </button>
            <button
              type="button"
              onClick={getAiRecommendations}
              disabled={recommendState === "loading"}
              className="whitespace-nowrap border border-accent-press bg-accent-deep px-3 py-[7px] font-display text-[11.5px] font-semibold uppercase tracking-[.05em] text-ground hover:bg-accent-press disabled:opacity-50"
            >
              {recommendState === "loading" ? "Thinking…" : "AI-recommend budgets"}
            </button>
          </div>
        )}
        {recommendState === "error" && <p className="mb-4 text-[13px] text-crit">{recommendError}</p>}

        {recommendation && (
          <div className="mb-6 border border-hairline bg-surface p-4">
            <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
              <div className="flex items-baseline gap-2">
                <span className="font-mono text-[10px] font-medium uppercase tracking-[.12em] text-ink-faint">
                  AI recommendation
                </span>
                <span
                  className="font-mono text-[10px]"
                  style={{ color: recommendation.source === "ai" ? "var(--good)" : "var(--warn)" }}
                >
                  {recommendation.source === "ai" ? "· from Claude" : "· estimated (AI unavailable right now)"}
                </span>
              </div>
              {recommendation.recommendations.length > 0 && (
                <button
                  type="button"
                  onClick={applyRecommendations}
                  className="whitespace-nowrap font-display text-[11.5px] font-semibold uppercase tracking-[.05em] text-accent-deep hover:text-accent-press"
                >
                  Apply all &rarr;
                </button>
              )}
            </div>
            <p className="m-0 mb-3 text-[13.5px] leading-[1.55] text-ink">{recommendation.summary}</p>
            {recommendation.recommendations.length > 0 && (
              <ul className="flex flex-col gap-2.5">
                {recommendation.recommendations.map((r) => (
                  <li key={r.category} className="flex items-baseline justify-between gap-4 border-t border-rule pt-2.5">
                    <div className="flex flex-col gap-0.5">
                      <span className="flex items-center gap-2 text-[13.5px] text-ink">
                        <span className="h-2 w-2 flex-none" style={{ background: CATEGORY_VAR[r.category] }} />
                        {r.category}
                      </span>
                      <span className="text-[12px] text-ink-faint">{r.rationale}</span>
                    </div>
                    <span className="num flex-none text-[15px] font-medium text-ink">
                      {currency(r.recommended_budget)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        <div className="flex flex-col">
          <div className="grid grid-cols-[1fr_124px_92px] gap-3.5 border-b border-hairline pb-[9px] font-mono text-[10px] font-medium uppercase tracking-[.1em] text-ink-faint">
            <span>Category</span>
            <span className="text-right">Monthly budget</span>
            <span className="text-right">Avg. spend</span>
          </div>
          {CATEGORIES.map((category) => (
            <div
              key={category}
              className="grid grid-cols-[1fr_124px_92px] items-center gap-3.5 border-b border-rule py-[11px]"
            >
              <span className="flex items-center gap-2.5 text-[14px] text-ink">
                <span className="h-2.5 w-2.5 flex-none" style={{ background: CATEGORY_VAR[category] }} />
                {category}
              </span>
              <span className="flex h-[38px] items-center gap-1.5 border border-field bg-surface px-2.5 focus-within:border-accent">
                <span className="font-mono text-[13px] text-ink-faint">$</span>
                <input
                  type="number"
                  min="0"
                  step="1"
                  value={valueFor(category)}
                  onChange={(e) => setDrafts((d) => ({ ...d, [category]: e.target.value }))}
                  className="num w-full border-0 bg-transparent text-right text-[14px] text-ink outline-none"
                />
              </span>
              <span className="num text-right text-[13px] text-ink-faint">
                {currency(Math.round(averages[category] ?? 0))}
              </span>
            </div>
          ))}
        </div>

        <div className="mt-[22px] flex flex-wrap items-center justify-between gap-3.5">
          <span className="whitespace-nowrap text-[13.5px] text-ink-muted">
            Total budgeted <strong className="num font-medium text-ink">{currency(totalBudgeted)}</strong> / month
          </span>
          <span className="flex flex-none gap-2.5">
            <button
              onClick={() => setDrafts({})}
              className="whitespace-nowrap border border-field px-4 py-[11px] font-display text-[13px] font-semibold uppercase tracking-[.04em] text-ink hover:bg-sunken"
            >
              Reset
            </button>
            <button
              onClick={saveAll}
              disabled={saving || Object.keys(drafts).length === 0}
              className="whitespace-nowrap border border-accent-press bg-accent-deep px-[18px] py-[11px] font-display text-[13px] font-semibold uppercase tracking-[.04em] text-ground hover:bg-accent-press disabled:opacity-50"
            >
              {saving ? "Saving…" : "Save budgets"}
            </button>
          </span>
        </div>
      </div>
    </div>
  );
}
