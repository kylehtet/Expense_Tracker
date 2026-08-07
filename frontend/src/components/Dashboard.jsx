import { useEffect, useState } from "react";
import { api } from "../api";
import { CategorySpendingChart } from "./CategorySpendingChart";
import { BudgetProgressList } from "./BudgetProgressBar";
import { TransactionsList } from "./TransactionsList";

export function Dashboard({ userId, refreshKey, onSyncRequested }) {
  const [budgetStatus, setBudgetStatus] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [syncState, setSyncState] = useState("idle"); // idle | syncing | error
  const [syncMessage, setSyncMessage] = useState(null);

  useEffect(() => {
    api.getBudgetStatus(userId).then(setBudgetStatus).catch(() => setBudgetStatus({}));
    api
      .getTransactions(userId)
      .then(setTransactions)
      .catch(() => setTransactions([]));
  }, [userId, refreshKey]);

  const handleSync = async () => {
    setSyncState("syncing");
    setSyncMessage(null);
    try {
      const { synced_count } = await api.sync(userId);
      setSyncMessage(`Synced ${synced_count} transactions.`);
      onSyncRequested();
    } catch (err) {
      setSyncMessage(err.status === 429 ? err.message : "Sync failed. Try again in a moment.");
    } finally {
      setSyncState("idle");
    }
  };

  const spendByCategory = Object.fromEntries(
    Object.entries(budgetStatus ?? {}).map(([category, entry]) => [category, entry.actual])
  );

  return (
    <div className="flex flex-col gap-8">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">This month</h2>
        <button
          onClick={handleSync}
          disabled={syncState === "syncing"}
          className="rounded px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
          style={{ background: "var(--series-housing)" }}
        >
          {syncState === "syncing" ? "Syncing…" : "Sync now"}
        </button>
      </div>
      {syncMessage && <p className="text-sm text-[var(--text-secondary)]">{syncMessage}</p>}

      <section className="flex flex-col gap-3">
        <h3 className="text-sm font-semibold text-[var(--text-secondary)]">Spending by category</h3>
        {budgetStatus ? <CategorySpendingChart spendByCategory={spendByCategory} /> : null}
      </section>

      <section className="flex flex-col gap-3">
        <h3 className="text-sm font-semibold text-[var(--text-secondary)]">Budget progress</h3>
        {budgetStatus ? <BudgetProgressList status={budgetStatus} /> : null}
      </section>

      <section className="flex flex-col gap-3">
        <h3 className="text-sm font-semibold text-[var(--text-secondary)]">Recent transactions</h3>
        <TransactionsList transactions={transactions.slice(0, 20)} />
      </section>
    </div>
  );
}
