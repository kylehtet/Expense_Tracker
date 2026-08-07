import { useEffect, useState } from "react";
import { api } from "./api";
import { getUserId } from "./userId";
import { SandboxBanner } from "./components/SandboxBanner";
import { Disclaimer, PrivacyNote } from "./components/Disclaimer";
import { ConnectBankButton } from "./components/ConnectBankButton";
import { Dashboard } from "./components/Dashboard";
import { BudgetSettings } from "./components/BudgetSettings";

const LINKED_KEY_PREFIX = "expense_tracker_linked_";

function App() {
  const [userId] = useState(getUserId);
  const [config, setConfig] = useState(null);
  const [linked, setLinked] = useState(() => localStorage.getItem(LINKED_KEY_PREFIX + userId) === "true");
  const [tab, setTab] = useState("dashboard");
  const [refreshKey, setRefreshKey] = useState(0);
  const [budgetStatus, setBudgetStatus] = useState({});

  useEffect(() => {
    api.getConfig().then(setConfig).catch(() => setConfig({ is_sandbox: true }));
  }, []);

  useEffect(() => {
    if (linked) {
      api.getBudgetStatus(userId).then(setBudgetStatus).catch(() => {});
    }
  }, [userId, linked, refreshKey]);

  const handleLinked = async () => {
    localStorage.setItem(LINKED_KEY_PREFIX + userId, "true");
    setLinked(true);
    try {
      await api.sync(userId);
    } catch {
      // First sync-after-link failures aren't fatal - the dashboard's own
      // "Sync now" button covers retrying.
    }
    setRefreshKey((k) => k + 1);
  };

  return (
    <div className="min-h-screen">
      <SandboxBanner isSandbox={config?.is_sandbox} />

      <header className="mx-auto flex max-w-3xl items-center justify-between px-6 py-6">
        <h1 className="text-xl font-semibold">Expense Tracker</h1>
        {linked && (
          <nav className="flex gap-4 text-sm">
            <button
              onClick={() => setTab("dashboard")}
              className={tab === "dashboard" ? "font-semibold" : "text-[var(--text-muted)]"}
            >
              Dashboard
            </button>
            <button
              onClick={() => setTab("settings")}
              className={tab === "settings" ? "font-semibold" : "text-[var(--text-muted)]"}
            >
              Settings
            </button>
          </nav>
        )}
      </header>

      <main className="mx-auto flex max-w-3xl flex-col gap-8 px-6 pb-16">
        {!linked ? (
          <div
            className="flex flex-col items-start gap-4 rounded-lg border p-6"
            style={{ borderColor: "var(--gridline)", background: "var(--surface-1)" }}
          >
            <p className="text-sm text-[var(--text-secondary)]">
              Connect a bank account to see your spending, categorized automatically.
            </p>
            <ConnectBankButton userId={userId} onLinked={handleLinked} />
          </div>
        ) : tab === "dashboard" ? (
          <Dashboard userId={userId} refreshKey={refreshKey} onSyncRequested={() => setRefreshKey((k) => k + 1)} />
        ) : (
          <section className="flex flex-col gap-3">
            <h2 className="text-lg font-semibold">Monthly budgets</h2>
            <BudgetSettings userId={userId} budgets={budgetStatus} onSaved={() => setRefreshKey((k) => k + 1)} />
          </section>
        )}

        <footer className="flex flex-col gap-2 border-t pt-4" style={{ borderColor: "var(--gridline)" }}>
          <Disclaimer />
          <PrivacyNote />
        </footer>
      </main>
    </div>
  );
}

export default App;
