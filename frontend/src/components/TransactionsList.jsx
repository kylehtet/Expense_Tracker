const currency = (amount) => {
  const sign = amount < 0 ? "+" : "";
  return `${sign}$${Math.abs(amount).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

export function TransactionsList({ transactions }) {
  if (transactions.length === 0) {
    return <p className="text-sm text-[var(--text-muted)]">No transactions synced yet.</p>;
  }

  return (
    <ul className="flex flex-col divide-y" style={{ borderColor: "var(--gridline)" }}>
      {transactions.map((t) => (
        <li key={t.transaction_id} className="flex items-center justify-between gap-4 py-2">
          <div className="flex min-w-0 flex-col">
            <span className="truncate text-sm text-[var(--text-primary)]">{t.merchant_name || t.name}</span>
            <span className="text-xs text-[var(--text-muted)]">
              {t.date} · {t.category}
            </span>
          </div>
          <span
            className="shrink-0 text-sm tabular-nums"
            style={{ color: t.amount < 0 ? "var(--status-good)" : "var(--text-primary)" }}
          >
            {currency(t.amount)}
          </span>
        </li>
      ))}
    </ul>
  );
}
