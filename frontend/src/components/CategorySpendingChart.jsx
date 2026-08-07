const CATEGORY_COLOR = {
  Housing: "var(--series-housing)",
  Food: "var(--series-food)",
  Transport: "var(--series-transport)",
  Subscriptions: "var(--series-subscriptions)",
  Entertainment: "var(--series-entertainment)",
  Other: "var(--series-other)",
};

const currency = (value) => `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

export function CategorySpendingChart({ spendByCategory }) {
  // Only positive spend is meaningful on this chart - refunds/income (negative
  // net amounts) don't have a "how much did I spend" bar to draw.
  const bars = Object.entries(spendByCategory)
    .filter(([, amount]) => amount > 0)
    .sort(([, a], [, b]) => b - a);

  if (bars.length === 0) {
    return <p className="text-sm text-[var(--text-muted)]">No spending yet this period.</p>;
  }

  const max = Math.max(...bars.map(([, amount]) => amount));

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-2" role="img" aria-label="Spending by category">
        {bars.map(([category, amount]) => (
          <div key={category} className="flex items-center gap-3">
            <span className="w-28 shrink-0 text-sm text-[var(--text-secondary)]">{category}</span>
            <div className="h-4 flex-1 overflow-hidden rounded" style={{ background: "var(--gridline)" }}>
              <div
                className="h-full rounded transition-[width]"
                style={{
                  width: `${(amount / max) * 100}%`,
                  background: CATEGORY_COLOR[category] ?? "var(--text-muted)",
                }}
                title={`${category}: ${currency(amount)}`}
              />
            </div>
            <span className="w-16 shrink-0 text-right text-sm tabular-nums text-[var(--text-primary)]">
              {currency(amount)}
            </span>
          </div>
        ))}
      </div>

      <details className="text-xs text-[var(--text-muted)]">
        <summary className="cursor-pointer select-none text-[var(--text-secondary)]">View as table</summary>
        <table className="mt-2 w-full text-left text-sm">
          <thead>
            <tr className="text-[var(--text-secondary)]">
              <th className="py-1">Category</th>
              <th className="py-1 text-right">Amount</th>
            </tr>
          </thead>
          <tbody>
            {bars.map(([category, amount]) => (
              <tr key={category} className="border-t" style={{ borderColor: "var(--gridline)" }}>
                <td className="py-1">{category}</td>
                <td className="py-1 text-right tabular-nums">{currency(amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  );
}
