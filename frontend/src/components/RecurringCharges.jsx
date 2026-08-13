import { useEffect, useState } from "react";
import { api } from "../api";

const VERDICT_TOKEN = {
  over: { fg: "var(--crit)", bg: "var(--crit-bg)", br: "var(--crit-br)", label: "Over" },
  tight: { fg: "var(--warn)", bg: "var(--warn-bg)", br: "var(--warn-br)", label: "Tight" },
  comfortable: { fg: "var(--good)", bg: "var(--good-bg)", br: "var(--good-br)", label: "Fine" },
};

const MAX_FLAGGED_SHOWN = 5;

const currency = (value) => `$${Math.abs(value).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;

function impactText(impacts) {
  if (!impacts || impacts.length === 0) return null;
  const top = impacts[0];
  if (top.newly_reachable) return `Could make ${top.goal_name} reachable for the first time (~${top.hypothetical_months_to_goal}mo).`;
  const months = top.months_sooner;
  return `Could get ${top.goal_name} there ~${months} mo sooner.`;
}

function RecurringRow({ charge, onDismiss }) {
  const token = VERDICT_TOKEN[charge.verdict] ?? VERDICT_TOKEN.comfortable;
  const impact = impactText(charge.impact_on_goals);

  return (
    <div className="rounded-xl border-2 px-4 py-3" style={{ borderColor: token.br, background: token.bg }}>
      <div className="flex items-center justify-between gap-2">
        <span className="flex min-w-0 items-center gap-2">
          <span
            className="rounded-full font-display text-[9.5px] font-bold uppercase tracking-[.04em]"
            style={{ color: token.fg, padding: "3px 8px", background: "color-mix(in srgb, currentColor 14%, transparent)" }}
          >
            {token.label}
          </span>
          <span className="truncate font-display text-[14px] font-semibold text-ink">{charge.merchant}</span>
        </span>
        <span className="flex flex-none items-center gap-2.5">
          <span className="num text-[13.5px] font-semibold text-ink">{currency(charge.average_amount)}/mo</span>
          <button
            type="button"
            onClick={onDismiss}
            aria-label={`Dismiss ${charge.merchant}`}
            className="text-[11px] text-ink-faint hover:text-ink"
          >
            &#10005;
          </button>
        </span>
      </div>
      {impact && (
        <p className="m-0 mt-1.5 text-[12px]" style={{ color: "var(--accent-deep)" }}>
          {impact}
        </p>
      )}
    </div>
  );
}

export function RecurringCharges({ goals }) {
  const [charges, setCharges] = useState([]);
  const [dismissed, setDismissed] = useState([]);

  useEffect(() => {
    api
      .getRecurring()
      .then(setCharges)
      .catch(() => setCharges([]));
    // Goal-impact math depends on the current goals list - refetch whenever
    // it changes so a newly created/updated goal's impact shows up here
    // without needing a page reload.
  }, [goals]);

  const visible = charges.filter((c) => !dismissed.includes(c.merchant));
  if (visible.length === 0) return null;

  const flagged = visible
    .filter((c) => c.verdict === "over")
    .concat(visible.filter((c) => c.verdict === "tight"))
    .slice(0, MAX_FLAGGED_SHOWN);
  const restCount = visible.length - flagged.length;

  return (
    <div className="flex flex-col">
      <h3 className="mb-3 font-display text-[16px] font-bold uppercase tracking-[.05em] text-ink">Found in your spending</h3>
      {flagged.length === 0 ? (
        <p className="text-[13.5px] text-ink-faint">All {visible.length} recurring charges fit fine.</p>
      ) : (
        <div className="flex flex-col gap-2">
          {flagged.map((c) => (
            <RecurringRow key={c.merchant} charge={c} onDismiss={() => setDismissed((d) => [...d, c.merchant])} />
          ))}
        </div>
      )}
      {restCount > 0 && <p className="mt-2.5 text-[12px] text-ink-faint">+{restCount} more, fitting fine</p>}
    </div>
  );
}
