import { useState } from "react";
import { CategorySpendingChart } from "./CategorySpendingChart";
import { BudgetProgressList } from "./BudgetProgressBar";
import { TransactionsList } from "./TransactionsList";
import { Corners } from "./Corners";

const currency = (value) =>
  `$${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const monthLabel = () =>
  new Date().toLocaleDateString(undefined, { month: "long", year: "numeric" });

function GoalWarningBanner({ goals }) {
  const offTrack = goals.filter((g) => !g.health.on_track);
  const offTrackIds = offTrack.map((g) => g.id).sort().join(",");
  // Keyed by the *set* of off-track goal ids, so the banner re-surfaces if a
  // new goal falls behind even after an earlier, different set was dismissed.
  const [dismissedFor, setDismissedFor] = useState("");

  if (offTrack.length === 0 || dismissedFor === offTrackIds) return null;

  const names = offTrack.map((g) => g.name).join(", ");

  return (
    <div className="flex items-start justify-between gap-4 border border-crit-br bg-crit-bg px-[22px] py-3.5">
      <p className="m-0 text-[13.5px] leading-[1.5] text-crit">
        <strong className="font-semibold">Behind pace: </strong>
        {names} {offTrack.length === 1 ? "isn't" : "aren't"} on track to hit their target — check Affordability &rsaquo;
        Your goals for details.
      </p>
      <button
        type="button"
        onClick={() => setDismissedFor(offTrackIds)}
        className="flex-none font-display text-[11px] font-semibold uppercase tracking-[.06em] text-crit hover:opacity-70"
      >
        Dismiss
      </button>
    </div>
  );
}

export function Dashboard({ status, transactions, goals = [] }) {
  const entries = Object.values(status);
  const totalSpent = entries.reduce((sum, e) => sum + Math.max(e.actual, 0), 0);
  const budgeted = entries.filter((e) => e.budget != null);
  const totalBudget = budgeted.reduce((sum, e) => sum + e.budget, 0);
  const totalSpentBudgeted = budgeted.reduce((sum, e) => sum + e.actual, 0);
  const leftToSpend = totalBudget - totalSpentBudgeted;
  const overCount = entries.filter((e) => e.status === "over").length;
  const dailyPace = totalSpent / new Date().getDate();

  const stats = [
    { label: "Left to spend", value: currency(leftToSpend), color: leftToSpend < 0 ? "var(--crit)" : "var(--good)" },
    { label: "Over budget", value: `${overCount} cat.`, color: overCount > 0 ? "var(--crit)" : "var(--ink)" },
    { label: "Daily pace", value: currency(dailyPace), color: "var(--ink)" },
  ];

  return (
    <div className="flex flex-col gap-5">
      <GoalWarningBanner goals={goals} />

      <div className="blueprint relative border border-hairline bg-ground">
        <Corners />

        <div className="flex flex-wrap items-end justify-between gap-7 border-b border-rule px-[30px] py-6">
          <div>
            <div className="mb-2.5 font-mono text-[10px] font-medium uppercase tracking-[.14em] text-ink-faint">
              {monthLabel()} &middot; to date
            </div>
            <div className="flex items-baseline gap-3.5">
              <span className="font-display text-[46px] font-semibold tracking-[-.01em] text-ink num">
                {currency(totalSpent)}
              </span>
              {totalBudget > 0 && (
                <span className="text-[14px] text-ink-muted">spent of {currency(totalBudget)} budgeted</span>
              )}
            </div>
          </div>
          <div className="flex gap-px border border-hairline bg-hairline">
            {stats.map((s) => (
              <div key={s.label} className="min-w-[132px] bg-ground px-[22px] py-[13px]">
                <div className="mb-2 font-mono text-[10px] font-medium uppercase tracking-[.1em] text-ink-faint">
                  {s.label}
                </div>
                <div className="num font-display text-[23px] font-semibold" style={{ color: s.color }}>
                  {s.value}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 gap-px bg-rule lg:grid-cols-[1.18fr_1fr]">
          <div className="flex flex-col bg-ground">
            <section className="border-b border-rule px-[30px] py-[26px]">
              <div className="mb-5 flex items-baseline justify-between gap-3">
                <h3 className="font-display text-[16px] font-semibold uppercase tracking-[.07em] text-ink">
                  Spending by category
                </h3>
                <span className="font-mono text-[12.5px] text-ink-faint">ranked</span>
              </div>
              <CategorySpendingChart status={status} />
            </section>

            <section className="px-[30px] py-[26px]">
              <h3 className="mb-4 font-display text-[16px] font-semibold uppercase tracking-[.07em] text-ink">
                Budget progress
              </h3>
              <BudgetProgressList status={status} />
            </section>
          </div>

          <div className="flex flex-col bg-ground">
            <div className="flex items-center justify-between gap-3 px-[30px] pb-4 pt-[26px]">
              <h3 className="font-display text-[16px] font-semibold uppercase tracking-[.07em] text-ink">
                Recent transactions
              </h3>
            </div>
            <TransactionsList transactions={transactions.slice(0, 10)} />
          </div>
        </div>
      </div>
    </div>
  );
}
