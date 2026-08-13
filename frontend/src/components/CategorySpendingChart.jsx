const CATEGORY_VAR = {
  Housing: "var(--cat-housing)",
  Food: "var(--cat-food)",
  Entertainment: "var(--cat-entertainment)",
  Transport: "var(--cat-transport)",
  Other: "var(--cat-other)",
  Subscriptions: "var(--cat-subs)",
};

const currency = (value) => `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

export function CategorySpendingChart({ status, compact = false }) {
  const rows = Object.entries(status)
    .filter(([, entry]) => entry.actual > 0)
    .map(([category, entry]) => ({ category, ...entry }))
    .sort((a, b) => b.actual - a.actual);

  if (rows.length === 0) {
    return <p className="text-sm text-ink-faint">No spending yet this period.</p>;
  }

  const max = Math.max(...rows.map((r) => r.actual));
  const total = rows.reduce((sum, r) => sum + r.actual, 0);

  if (compact) {
    return (
      <div className="flex flex-col gap-2" role="img" aria-label="Spending by category, ranked">
        {rows.map((r, i) => (
          <div key={r.category} className="grid grid-cols-[14px_58px_1fr_42px] items-center gap-1.5 sm:grid-cols-[16px_80px_1fr_54px] sm:gap-2">
            <span className="num text-right text-[10.5px] text-ink-faint">{i + 1}</span>
            <span className="truncate text-[12px] text-ink">{r.category}</span>
            <span className="relative block h-3.5 rounded-full bg-track">
              <span
                className="absolute inset-y-0 left-0 rounded-full bg-accent"
                style={{ width: `${(r.actual / max) * 100}%` }}
              />
            </span>
            <span className="num text-right text-[12px] font-medium text-ink">{currency(r.actual)}</span>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3.5">
      <div className="flex flex-col gap-3.5" role="img" aria-label="Spending by category, ranked">
        {rows.map((r, i) => (
          <div key={r.category} className="grid grid-cols-[18px_72px_1fr_58px_32px] items-center gap-2 sm:grid-cols-[22px_106px_1fr_86px_46px] sm:gap-3.5">
            <span className="num text-right text-[12px] text-ink-faint">{i + 1}</span>
            <span className="truncate text-[14px] text-ink">{r.category}</span>
            <span className="relative block h-5 bg-track">
              <span
                className="absolute inset-y-0 left-0 bg-accent"
                style={{ width: `${(r.actual / max) * 100}%` }}
              />
            </span>
            <span className="num text-right text-[14px] font-medium text-ink">{currency(r.actual)}</span>
            <span className="num text-right text-[12.5px] text-ink-faint">
              {Math.round((r.actual / total) * 100)}%
            </span>
          </div>
        ))}
      </div>

      <div className="mt-1.5 border-t border-rule pt-[22px]">
        <div className="mb-3 font-mono text-[10px] font-medium uppercase tracking-[.12em] text-ink-faint">
          Share of total
        </div>
        <div className="flex h-[26px] w-full border border-hairline">
          {rows.map((r) => (
            <span
              key={r.category}
              className="block"
              style={{ width: `${(r.actual / total) * 100}%`, background: CATEGORY_VAR[r.category] }}
            />
          ))}
        </div>
        <div className="mt-3.5 flex flex-wrap gap-x-[22px] gap-y-2.5">
          {rows.map((r) => (
            <span key={r.category} className="inline-flex items-center gap-[7px] text-[13px] text-ink">
              <span className="size-2.5 shrink-0" style={{ background: CATEGORY_VAR[r.category] }} />
              {r.category}
              <span className="num text-[12.5px] text-ink-faint">{Math.round((r.actual / total) * 100)}%</span>
            </span>
          ))}
        </div>
      </div>

      <details className="mt-1">
        <summary className="cursor-pointer list-none font-display text-[12px] font-semibold uppercase tracking-[.06em] text-accent-deep">
          View as table &#8964;
        </summary>
        <div className="mt-3 flex flex-col">
          <div className="grid grid-cols-[1fr_64px_46px] gap-2 border-b border-hairline pb-2 font-mono text-[10px] font-medium uppercase tracking-[.1em] text-ink-faint sm:grid-cols-[1fr_92px_60px_92px] sm:gap-3">
            <span>Category</span>
            <span className="text-right">Spent</span>
            <span className="text-right">Share</span>
            <span className="hidden text-right sm:block">Budget</span>
          </div>
          {rows.map((r) => (
            <div
              key={r.category}
              className="grid grid-cols-[1fr_64px_46px] gap-2 border-b border-rule py-2.5 text-[13.5px] text-ink sm:grid-cols-[1fr_92px_60px_92px] sm:gap-3"
            >
              <span>{r.category}</span>
              <span className="num text-right">{currency(r.actual)}</span>
              <span className="num text-right text-ink-muted">{Math.round((r.actual / total) * 100)}%</span>
              <span className="num hidden text-right text-ink-muted sm:block">
                {r.budget != null ? currency(r.budget) : "—"}
              </span>
            </div>
          ))}
        </div>
      </details>
    </div>
  );
}
