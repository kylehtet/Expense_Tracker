const STATUS_TOKEN = {
  under: { fg: "var(--good)", bg: "var(--good-bg)", br: "var(--good-br)", label: "Under" },
  on_track: { fg: "var(--warn)", bg: "var(--warn-bg)", br: "var(--warn-br)", label: "On track" },
  over: { fg: "var(--crit)", bg: "var(--crit-bg)", br: "var(--crit-br)", label: "Over" },
};

const currency = (value) => `$${Math.abs(value).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;

function monthProgress() {
  const now = new Date();
  const daysInMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate();
  return now.getDate() / daysInMonth;
}

export function BudgetProgressBar({ category, entry, compact = false }) {
  const pace = monthProgress();

  if (entry.status === "unbudgeted") {
    return (
      <div className={compact ? "flex flex-col gap-1.5 border-t border-rule py-2" : "flex flex-col gap-2.5 border-t border-rule py-3.5"}>
        <div className="flex items-baseline justify-between gap-3">
          <span className={compact ? "text-[12.5px] text-ink" : "text-[14.5px] text-ink"}>{category}</span>
          <span className="flex items-baseline gap-[9px]">
            <span className={compact ? "num text-[11.5px] font-medium text-ink-muted" : "num text-[13px] font-medium text-ink-muted"}>
              {currency(entry.actual)}
            </span>
            {!compact && (
              <span className="border border-dashed border-field bg-sunken px-2 py-[5px] font-display text-[10.5px] font-semibold uppercase tracking-[.08em] text-ink-muted">
                No budget set
              </span>
            )}
          </span>
        </div>
        <span className={compact ? "block h-1.5 rounded-full bg-track" : "block h-2 bg-track"} />
        {!compact && <span className="text-[12.5px] text-ink-faint">Set a limit in Settings to start tracking this one.</span>}
      </div>
    );
  }

  const pct = Math.min(entry.pct_used ?? (entry.status === "over" ? 1 : 0), 1);
  const token = STATUS_TOKEN[entry.status] ?? STATUS_TOKEN.under;

  return (
    <div className={compact ? "flex flex-col gap-1.5 border-t border-rule py-2" : "flex flex-col gap-2.5 border-t border-rule py-3.5"}>
      <div className="flex items-baseline justify-between gap-3">
        <span className={compact ? "text-[12.5px] text-ink" : "text-[14.5px] text-ink"}>{category}</span>
        <span className="flex items-baseline gap-[9px]">
          <span className={compact ? "num text-[11.5px] font-medium text-ink-muted" : "num text-[13px] font-medium text-ink-muted"}>
            {currency(entry.actual)} / {currency(entry.budget)}
          </span>
          <span
            className={compact ? "rounded-full font-display text-[9px] font-bold uppercase tracking-[.05em]" : "border font-display text-[10.5px] font-semibold uppercase tracking-[.08em]"}
            style={
              compact
                ? { color: token.fg, background: token.bg, padding: "3px 7px" }
                : { color: token.fg, background: token.bg, borderColor: token.br, padding: "5px 8px" }
            }
          >
            {token.label}
          </span>
        </span>
      </div>
      <span className={compact ? "relative block h-1.5 rounded-full bg-track" : "relative block h-2 bg-track"}>
        <span className={compact ? "absolute inset-y-0 left-0 rounded-full" : "absolute inset-y-0 left-0"} style={{ width: `${pct * 100}%`, background: token.fg }} />
        {!compact && (
          <span
            className="absolute -inset-y-[3px] w-px bg-ink opacity-45"
            style={{ left: `${pace * 100}%` }}
            title="Month-to-date pace"
          />
        )}
      </span>
    </div>
  );
}

export function BudgetProgressList({ status, compact = false }) {
  const categories = Object.keys(status).sort();
  if (categories.length === 0) {
    return <p className="text-sm text-ink-faint">No spending yet this period.</p>;
  }
  return (
    <div className="flex flex-col">
      {categories.map((category) => (
        <BudgetProgressBar key={category} category={category} entry={status[category]} compact={compact} />
      ))}
      {!compact && (
        <p className="mt-3 text-[12.5px] text-ink-faint">
          The hairline marks month-to-date pace. Bars past it are running hot.
        </p>
      )}
    </div>
  );
}
