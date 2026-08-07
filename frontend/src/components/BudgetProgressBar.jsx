const STATUS_COLOR = {
  under: "var(--status-good)",
  on_track: "var(--status-warning)",
  over: "var(--status-critical)",
  unbudgeted: "var(--text-muted)",
};

const STATUS_LABEL = {
  under: "Under budget",
  on_track: "On track",
  over: "Over budget",
  unbudgeted: "No budget set",
};

const currency = (value) =>
  value == null ? "—" : `$${Math.abs(value).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

export function BudgetProgressBar({ category, entry }) {
  const pct = entry.pct_used == null ? (entry.status === "over" ? 1 : 0) : Math.min(entry.pct_used, 1);
  const color = STATUS_COLOR[entry.status] ?? "var(--text-muted)";

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-baseline justify-between text-sm">
        <span className="font-medium text-[var(--text-primary)]">{category}</span>
        <span className="text-[var(--text-secondary)]">
          {currency(entry.actual)}
          {entry.budget != null && <> / {currency(entry.budget)}</>}
        </span>
      </div>
      <div
        role="progressbar"
        aria-label={`${category} spending`}
        aria-valuenow={Math.round(pct * 100)}
        aria-valuemin={0}
        aria-valuemax={100}
        className="h-2 w-full overflow-hidden rounded-full"
        style={{ background: "var(--gridline)" }}
      >
        <div
          className="h-full rounded-full transition-[width]"
          style={{ width: `${pct * 100}%`, background: color }}
        />
      </div>
      <span className="text-xs" style={{ color }}>
        {STATUS_LABEL[entry.status] ?? entry.status}
      </span>
    </div>
  );
}

export function BudgetProgressList({ status }) {
  const categories = Object.keys(status).sort();
  if (categories.length === 0) {
    return <p className="text-sm text-[var(--text-muted)]">No spending yet this period.</p>;
  }
  return (
    <div className="flex flex-col gap-4">
      {categories.map((category) => (
        <BudgetProgressBar key={category} category={category} entry={status[category]} />
      ))}
    </div>
  );
}
