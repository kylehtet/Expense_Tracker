import { useEffect, useState } from "react";
import { api } from "../api";

const CATEGORIES = ["Housing", "Food", "Transport", "Shopping", "Subscriptions", "Entertainment", "Other"];

const PACE_TOKEN = {
  ahead: { fg: "var(--good)", bg: "var(--good-bg)", br: "var(--good-br)", label: "Ahead of pace" },
  on_pace: { fg: "var(--good)", bg: "var(--good-bg)", br: "var(--good-br)", label: "On track" },
  behind: { fg: "var(--crit)", bg: "var(--crit-bg)", br: "var(--crit-br)", label: "Behind pace" },
};

const currency = (value) =>
  value == null
    ? "—"
    : `${value < 0 ? "−" : ""}$${Math.abs(value).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;

function NewGoalForm({ onChanged, onClose }) {
  const [name, setName] = useState("");
  const [targetAmount, setTargetAmount] = useState("");
  const [category, setCategory] = useState("Other");
  const [targetDate, setTargetDate] = useState("");
  const [currentSaved, setCurrentSaved] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const save = async () => {
    const amount = Number(targetAmount);
    if (!name.trim()) {
      setError("Give the goal a name.");
      return;
    }
    if (!Number.isFinite(amount) || amount <= 0) {
      setError("Enter a target amount greater than $0.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await api.createGoal({
        name: name.trim(),
        targetAmount: amount,
        category,
        targetDate: targetDate || undefined,
        currentSaved: currentSaved ? Number(currentSaved) : 0,
      });
      await onChanged();
      onClose();
    } catch (err) {
      setError(err.message || "Couldn't save that goal. Try again.");
      setSaving(false);
    }
  };

  return (
    <div className="mb-5 rounded-2xl border-2 border-hairline bg-sunken px-6 py-6">
      <div className="mb-4 flex items-baseline justify-between gap-3">
        <h4 className="font-display text-[13px] font-semibold uppercase tracking-[.06em] text-ink">New goal</h4>
        <button type="button" onClick={onClose} className="text-[11.5px] text-ink-faint hover:text-ink">
          Cancel
        </button>
      </div>

      <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <label className="mb-1.5 block font-mono text-[10px] font-medium uppercase tracking-[.1em] text-ink-faint">
            Name
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. PS5, Flight to Tokyo"
            className="h-10 w-full rounded-xl border-2 border-field bg-ground px-3 text-[13.5px] text-ink outline-none focus:border-accent"
          />
        </div>

        <div>
          <label className="mb-1.5 block font-mono text-[10px] font-medium uppercase tracking-[.1em] text-ink-faint">
            Target amount
          </label>
          <div className="flex h-10 items-center gap-1.5 rounded-xl border-2 border-field bg-ground px-3 focus-within:border-accent">
            <span className="font-mono text-[13px] text-ink-faint">$</span>
            <input
              type="number"
              min="0"
              step="1"
              value={targetAmount}
              onChange={(e) => setTargetAmount(e.target.value)}
              className="num w-full border-0 bg-transparent text-[13.5px] text-ink outline-none"
            />
          </div>
        </div>

        <div>
          <label className="mb-1.5 block font-mono text-[10px] font-medium uppercase tracking-[.1em] text-ink-faint">
            Already saved <span className="normal-case text-ink-faint">(optional)</span>
          </label>
          <div className="flex h-10 items-center gap-1.5 rounded-xl border-2 border-field bg-ground px-3 focus-within:border-accent">
            <span className="font-mono text-[13px] text-ink-faint">$</span>
            <input
              type="number"
              min="0"
              step="1"
              value={currentSaved}
              onChange={(e) => setCurrentSaved(e.target.value)}
              className="num w-full border-0 bg-transparent text-[13.5px] text-ink outline-none"
            />
          </div>
        </div>

        <div className="sm:col-span-2">
          <label className="mb-1.5 block font-mono text-[10px] font-medium uppercase tracking-[.1em] text-ink-faint">
            Category
          </label>
          <div className="flex flex-wrap gap-2">
            {CATEGORIES.map((c) => (
              <button
                key={c}
                type="button"
                onClick={() => setCategory(c)}
                aria-pressed={category === c}
                className="whitespace-nowrap rounded-full border-2 px-3.5 py-2 font-display text-[11px] font-semibold uppercase tracking-[.05em]"
                style={
                  category === c
                    ? { borderColor: "var(--accent)", background: "var(--accent-tint)", color: "var(--accent-deep)" }
                    : { borderColor: "var(--field)", background: "transparent", color: "var(--ink)" }
                }
              >
                {c}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="mb-1.5 block font-mono text-[10px] font-medium uppercase tracking-[.1em] text-ink-faint">
            Target date <span className="normal-case text-ink-faint">(optional)</span>
          </label>
          <input
            type="date"
            value={targetDate}
            onChange={(e) => setTargetDate(e.target.value)}
            className="h-10 w-full rounded-xl border-2 border-field bg-ground px-3 text-[13.5px] text-ink outline-none focus:border-accent"
          />
        </div>
      </div>

      {error && <p className="mt-3 text-[13px] text-crit">{error}</p>}

      <button
        type="button"
        onClick={save}
        disabled={saving}
        className="mt-4 whitespace-nowrap rounded-full border-2 border-accent-press bg-accent-deep px-6 py-2.5 font-display text-[12.5px] font-bold uppercase tracking-[.05em] text-ground disabled:opacity-50"
      >
        {saving ? "Saving…" : "Save goal"}
      </button>
    </div>
  );
}

function AutoBudgetPanel({ goalId, onApplied, location }) {
  const [state, setState] = useState("loading"); // loading | ready | applying | applied | error
  const [data, setData] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getAutoBudget(goalId, location)
      .then((d) => {
        if (!cancelled) {
          setData(d);
          setState("ready");
        }
      })
      .catch((err) => {
        if (cancelled) return;
        // Cooldown is per-user, not per-goal, so opening a second goal's plan
        // shortly after the first legitimately hits this - tell the user it's
        // transient instead of showing a generic, permanent-looking failure.
        if (err.status === 429) {
          const match = /retry after (\d+)s/.exec(err.message);
          setErrorMessage(match ? `Give it ${match[1]}s, then reopen this panel.` : "Give it a moment, then reopen this panel.");
        } else {
          setErrorMessage("Couldn't load a plan - try again later.");
        }
        setState("error");
      });
    return () => {
      cancelled = true;
    };
  }, [goalId, location]);

  const apply = async () => {
    setState("applying");
    try {
      await Promise.all(data.suggestions.map((s) => api.setBudget(s.category, s.suggested_budget)));
      await onApplied();
      setState("applied");
    } catch {
      setState("error");
    }
  };

  if (state === "loading") return <p className="mt-3 text-[13px] text-ink-faint">Working out a plan…</p>;
  if (state === "error") return <p className="mt-3 text-[13px] text-crit">{errorMessage}</p>;
  if (state === "applied") return <p className="mt-3 text-[13px] font-medium text-good">Applied - budgets updated.</p>;
  if (data.source === "not_needed") return <p className="mt-3 text-[13px] text-good">Already on pace for this goal.</p>;
  if (data.suggestions.length === 0) return <p className="mt-3 text-[13px] text-ink-faint">{data.summary}</p>;

  return (
    <div className="mt-3 rounded-xl border-2 border-hairline bg-sunken px-4 py-3.5">
      <p className="m-0 mb-2 text-[12.5px] font-semibold text-ink">Free up {currency(data.required_cut)}/mo:</p>
      <div className="flex flex-col gap-1.5">
        {data.suggestions.map((s) => (
          <div key={s.category} className="flex items-baseline justify-between gap-2 text-[12.5px]" title={s.rationale}>
            <span className="text-ink">{s.category}</span>
            <span className="num text-ink-muted">&rarr; {currency(s.suggested_budget)}/mo</span>
          </div>
        ))}
      </div>
      <button
        type="button"
        onClick={apply}
        disabled={state === "applying"}
        className="mt-3 w-full rounded-full border-2 border-accent-press bg-accent-deep py-2 font-display text-[11.5px] font-bold uppercase tracking-[.05em] text-ground disabled:opacity-50"
      >
        {state === "applying" ? "Applying…" : "Apply"}
      </button>
    </div>
  );
}

function goalToken(goal) {
  const achieved = goal.health.reason === "goal_achieved";
  return achieved ? PACE_TOKEN.on_pace : PACE_TOKEN[goal.health.pace_status] ?? PACE_TOKEN.on_pace;
}

function goalPct(goal) {
  return Math.min(goal.target_amount > 0 ? goal.current_saved / goal.target_amount : 0, 1);
}

// One shared line spanning every goal at once, with each goal plotted as a single
// benchmark dot at its progress % - an at-a-glance overview above the detailed cards,
// which stay the place to actually add funds, auto-budget, or abandon a goal.
function GoalsBenchmarkLine({ goals }) {
  if (goals.length === 0) return null;

  return (
    <div className="mb-6">
      <span className="relative mt-1 block h-2 rounded-full bg-track">
        {goals.map((g) => {
          const token = goalToken(g);
          return (
            <span
              key={g.id}
              title={`${g.name} — ${Math.round(goalPct(g) * 100)}%`}
              className="absolute top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-ground shadow-sm"
              style={{ left: `${goalPct(g) * 100}%`, background: token.fg }}
            />
          );
        })}
      </span>
      <div className="mt-4 flex flex-wrap gap-x-6 gap-y-2">
        {goals.map((g) => {
          const token = goalToken(g);
          return (
            <span key={g.id} className="flex items-center gap-1.5 text-[12.5px] text-ink-muted">
              <span className="h-2 w-2 flex-none rounded-full" style={{ background: token.fg }} />
              {g.name}
              <span className="num text-ink-faint">{Math.round(goalPct(g) * 100)}%</span>
            </span>
          );
        })}
      </div>
    </div>
  );
}

function GoalCard({ goal, onChanged, location }) {
  const [contribution, setContribution] = useState("");
  const [busy, setBusy] = useState(false);
  const [autoBudgetOpen, setAutoBudgetOpen] = useState(false);

  const pct = goalPct(goal);
  const achieved = goal.health.reason === "goal_achieved";
  const token = goalToken(goal);

  const addContribution = async () => {
    const amount = Number(contribution);
    if (!Number.isFinite(amount) || amount <= 0) return;
    setBusy(true);
    try {
      await api.updateGoal(goal.id, { current_saved: goal.current_saved + amount });
      setContribution("");
      await onChanged();
    } finally {
      setBusy(false);
    }
  };

  const abandon = async () => {
    setBusy(true);
    try {
      await api.abandonGoal(goal.id);
      await onChanged();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-2xl border-2 border-hairline bg-ground px-6 py-5">
      <div className="mb-1.5 flex items-baseline justify-between gap-3">
        <span className="font-display text-[17px] font-bold text-ink">{goal.name}</span>
        <span
          className="flex-none rounded-full font-display text-[10px] font-bold uppercase tracking-[.05em]"
          style={{ color: token.fg, background: token.bg, padding: "4px 10px" }}
        >
          {achieved ? "Goal reached" : token.label}
        </span>
      </div>
      <span className="num text-[13.5px] text-ink-muted">
        {currency(goal.current_saved)} / {currency(goal.target_amount)}
      </span>
      <span className="relative mt-2 block h-2.5 rounded-full bg-track">
        <span className="absolute inset-y-0 left-0 rounded-full" style={{ width: `${pct * 100}%`, background: token.fg }} />
      </span>

      <div className="mt-3.5 flex flex-wrap items-center gap-2">
        {!achieved && (
          <>
            <input
              type="number"
              min="0"
              placeholder="Add $"
              value={contribution}
              onChange={(e) => setContribution(e.target.value)}
              className="h-9 w-24 rounded-lg border-2 border-field bg-surface px-2.5 text-[13px] text-ink outline-none focus:border-accent"
            />
            <button
              type="button"
              onClick={addContribution}
              disabled={busy}
              className="h-9 flex-none rounded-lg border-2 border-field px-3 font-display text-[11px] font-semibold uppercase text-ink hover:bg-sunken disabled:opacity-50"
            >
              Add
            </button>
            <button
              type="button"
              onClick={() => setAutoBudgetOpen((o) => !o)}
              className="whitespace-nowrap rounded-full border-2 border-accent px-3.5 py-2 font-display text-[11px] font-bold uppercase tracking-[.04em] text-accent-deep hover:bg-accent-tint"
            >
              {autoBudgetOpen ? "Hide plan" : "Auto-budget"}
            </button>
          </>
        )}
        <button
          type="button"
          onClick={abandon}
          disabled={busy}
          className="ml-auto flex-none text-[12px] text-ink-faint underline decoration-dotted hover:text-crit"
        >
          Abandon
        </button>
      </div>

      {autoBudgetOpen && !achieved && <AutoBudgetPanel goalId={goal.id} onApplied={onChanged} location={location} />}
    </div>
  );
}

export function GoalsSection({ goals, onChanged, location }) {
  const [formOpen, setFormOpen] = useState(false);

  return (
    <div className="flex flex-col">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h3 className="font-display text-[16px] font-bold uppercase tracking-[.05em] text-ink">Your goals</h3>
        {!formOpen && (
          <button
            type="button"
            onClick={() => setFormOpen(true)}
            className="whitespace-nowrap rounded-full border-2 border-field px-4 py-2 font-display text-[11.5px] font-semibold uppercase tracking-[.04em] text-ink hover:bg-sunken"
          >
            + Add a goal
          </button>
        )}
      </div>

      {formOpen && <NewGoalForm onChanged={onChanged} onClose={() => setFormOpen(false)} />}

      {goals.length === 0 ? (
        !formOpen && <p className="text-[13.5px] text-ink-faint">No goals yet — add one above.</p>
      ) : (
        <>
          <GoalsBenchmarkLine goals={goals} />
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {goals.map((g) => (
              <GoalCard key={g.id} goal={g} onChanged={onChanged} location={location} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
