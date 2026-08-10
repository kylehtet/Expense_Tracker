import { useEffect, useState } from "react";
import { api } from "./api";
import { getUserId } from "./userId";
import { SandboxBanner } from "./components/SandboxBanner";
import { Footer } from "./components/Disclaimer";
import { ConnectBankButton } from "./components/ConnectBankButton";
import { Dashboard } from "./components/Dashboard";
import { BudgetSettings } from "./components/BudgetSettings";
import { Logo } from "./components/Logo";
import { LandingPage } from "./components/LandingPage";
import { AffordabilityChecker } from "./components/AffordabilityChecker";

const LINKED_KEY_PREFIX = "expense_tracker_linked_";
const SYNCED_AT_KEY_PREFIX = "expense_tracker_synced_at_";
const SYNC_COOLDOWN_MS = 60_000; // mirrors backend SYNC_COOLDOWN_SECONDS in main.py

const TABS = ["Dashboard", "Affordability", "Settings"];

function timeAgo(date) {
  if (!date) return null;
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function App() {
  const [userId] = useState(getUserId);
  const [config, setConfig] = useState(null);
  const [linked, setLinked] = useState(() => localStorage.getItem(LINKED_KEY_PREFIX + userId) === "true");
  const [showLanding, setShowLanding] = useState(
    () => localStorage.getItem(LINKED_KEY_PREFIX + userId) !== "true"
  );
  const [tab, setTab] = useState("Dashboard");
  const [refreshKey, setRefreshKey] = useState(0);
  const [status, setStatus] = useState({});
  const [transactions, setTransactions] = useState([]);
  const [syncState, setSyncState] = useState("idle"); // idle | syncing | error
  const [syncError, setSyncError] = useState(null);
  const [syncedAt, setSyncedAt] = useState(() => {
    const stored = localStorage.getItem(SYNCED_AT_KEY_PREFIX + userId);
    return stored ? new Date(stored) : null;
  });
  const [syncBlockedUntil, setSyncBlockedUntil] = useState(0);
  const [, forceTick] = useState(0);

  // Live-updating countdown while the sync button is cooling down, so
  // "rate limited" reads as a visible timer instead of a dead-end error.
  useEffect(() => {
    if (syncBlockedUntil <= Date.now()) return;
    const id = setInterval(() => {
      forceTick((n) => n + 1);
      if (Date.now() >= syncBlockedUntil) clearInterval(id);
    }, 1000);
    return () => clearInterval(id);
  }, [syncBlockedUntil]);

  useEffect(() => {
    api.getConfig().then(setConfig).catch(() => setConfig({ is_sandbox: true }));
  }, []);

  useEffect(() => {
    if (!linked) return;
    api.getBudgetStatus(userId).then(setStatus).catch(() => {});
    api
      .getTransactions(userId)
      .then(setTransactions)
      .catch(() => setTransactions([]));
  }, [userId, linked, refreshKey]);

  // Re-render every 30s so "Synced N min ago" stays fresh without a full refetch.
  useEffect(() => {
    const id = setInterval(() => forceTick((n) => n + 1), 30000);
    return () => clearInterval(id);
  }, []);

  const handleLinked = async () => {
    localStorage.setItem(LINKED_KEY_PREFIX + userId, "true");
    setLinked(true);
    await handleSync();
  };

  const handleSync = async () => {
    if (Date.now() < syncBlockedUntil) return;
    setSyncState("syncing");
    setSyncError(null);
    try {
      await api.sync(userId);
      const now = new Date();
      setSyncedAt(now);
      localStorage.setItem(SYNCED_AT_KEY_PREFIX + userId, now.toISOString());
      setSyncBlockedUntil(Date.now() + SYNC_COOLDOWN_MS);
      setRefreshKey((k) => k + 1);
    } catch (err) {
      if (err.status === 429) {
        const match = /retry after (\d+)s/.exec(err.message);
        setSyncBlockedUntil(Date.now() + (match ? Number(match[1]) * 1000 : SYNC_COOLDOWN_MS));
      } else {
        setSyncError("Sync failed. Try again in a moment.");
      }
    } finally {
      setSyncState("idle");
    }
  };

  const syncCooldownSeconds = Math.max(0, Math.ceil((syncBlockedUntil - Date.now()) / 1000));

  if (showLanding) {
    return <LandingPage onTryDemo={() => setShowLanding(false)} />;
  }

  return (
    <div className="flex min-h-screen flex-col bg-ground text-ink">
      <SandboxBanner isSandbox={config?.is_sandbox} />

      {linked && (
        <nav className="flex flex-wrap items-center gap-x-[30px] gap-y-1 border-b border-hairline bg-surface px-4 sm:px-[30px]">
          <Logo onClick={() => setShowLanding(true)} />
          <div className="flex gap-1">
            {TABS.map((label) => (
              <button
                key={label}
                onClick={() => setTab(label)}
                className="border-b-2 px-3.5 pb-[15px] pt-[18px] font-display text-[13px] font-semibold uppercase tracking-[.06em]"
                style={{
                  borderColor: tab === label ? "var(--accent)" : "transparent",
                  color: tab === label ? "var(--ink)" : "var(--ink-faint)",
                }}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="ml-auto flex items-center gap-3 py-2">
            <span className="num hidden text-[12.5px] text-ink-faint sm:inline">
              {syncState === "syncing" ? "Syncing…" : syncedAt ? `Synced ${timeAgo(syncedAt)}` : "Not synced yet"}
            </span>
            <button
              onClick={handleSync}
              disabled={syncState === "syncing" || syncCooldownSeconds > 0}
              className="whitespace-nowrap border border-field px-3.5 py-[9px] font-display text-[13px] font-semibold uppercase tracking-[.04em] text-ink hover:bg-sunken disabled:opacity-50"
            >
              {syncState === "syncing"
                ? "Syncing…"
                : syncCooldownSeconds > 0
                  ? `Sync again in ${syncCooldownSeconds}s`
                  : "Sync now"}
            </button>
          </div>
        </nav>
      )}
      {syncError && (
        <p className="bg-crit-bg px-[30px] py-2 text-[13px] text-crit">{syncError}</p>
      )}

      <main className="mx-auto flex w-full max-w-[1240px] flex-1 flex-col gap-8 px-6 py-8">
        {!linked ? (
          <ConnectBankButton userId={userId} onLinked={handleLinked} isSandbox={config?.is_sandbox} />
        ) : tab === "Dashboard" ? (
          <Dashboard status={status} transactions={transactions} />
        ) : tab === "Affordability" ? (
          <AffordabilityChecker userId={userId} isSandbox={config?.is_sandbox} />
        ) : (
          <BudgetSettings
            userId={userId}
            status={status}
            transactions={transactions}
            onSaved={() => setRefreshKey((k) => k + 1)}
          />
        )}
      </main>

      <Footer />
    </div>
  );
}

export default App;
