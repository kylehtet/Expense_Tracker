const CATEGORY_VAR = {
  Housing: "var(--cat-housing)",
  Food: "var(--cat-food)",
  Entertainment: "var(--cat-entertainment)",
  Transport: "var(--cat-transport)",
  Other: "var(--cat-other)",
  Subscriptions: "var(--cat-subs)",
};

const currency = (amount) => {
  const sign = amount < 0 ? "+" : "";
  return `${sign}$${Math.abs(amount).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

export function TransactionsList({ transactions, compact = false }) {
  if (transactions.length === 0) {
    return <p className="text-sm text-ink-faint">No transactions synced yet.</p>;
  }

  if (compact) {
    return (
      <ul className="flex flex-col">
        {transactions.map((t) => (
          <li
            key={t.transaction_id}
            className="flex items-center justify-between gap-2.5 border-t border-rule py-2 first:border-t-0"
          >
            <span className="flex min-w-0 items-center gap-2">
              <span
                className="h-2 w-2 flex-none rounded-full"
                style={{ background: CATEGORY_VAR[t.category] ?? "var(--cat-other)" }}
              />
              <span className="truncate text-[12.5px] text-ink">{t.merchant_name || t.name}</span>
            </span>
            <span
              className="num flex-none text-[12.5px]"
              style={{ color: t.amount < 0 ? "var(--good)" : "var(--ink)" }}
            >
              {currency(t.amount)}
            </span>
          </li>
        ))}
      </ul>
    );
  }

  return (
    <ul className="flex flex-col">
      {transactions.map((t) => (
        <li
          key={t.transaction_id}
          className="grid grid-cols-[1fr_auto] items-center gap-3.5 border-t border-rule px-[30px] py-3.5 hover:bg-sunken"
        >
          <span className="flex min-w-0 items-center gap-[13px]">
            <span
              className="h-2.5 w-2.5 flex-none"
              style={{ background: CATEGORY_VAR[t.category] ?? "var(--cat-other)" }}
            />
            <span className="flex min-w-0 flex-col gap-[3px]">
              <span className="truncate text-[14.5px] text-ink">{t.merchant_name || t.name}</span>
              <span className="text-[12.5px] text-ink-faint">
                {t.category} &middot; {t.date}
              </span>
            </span>
          </span>
          <span
            className="num text-[14.5px]"
            style={{ color: t.amount < 0 ? "var(--good)" : "var(--ink)" }}
          >
            {currency(t.amount)}
          </span>
        </li>
      ))}
    </ul>
  );
}
