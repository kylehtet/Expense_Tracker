import { useState } from "react";
import { api } from "../api";

const PACE_TOKEN = {
  ahead: { fg: "var(--good)", bg: "var(--good-bg)", br: "var(--good-br)", label: "Ahead of pace" },
  on_pace: { fg: "var(--good)", bg: "var(--good-bg)", br: "var(--good-br)", label: "On track" },
  behind: { fg: "var(--crit)", bg: "var(--crit-bg)", br: "var(--crit-br)", label: "Behind pace" },
};

const currency = (value) =>
  value == null
    ? "—"
    : `${value < 0 ? "−" : ""}$${Math.abs(value).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;

function formatMonth(iso) {
  if (!iso) return null;
  const [year, month] = iso.split("-").map(Number);
  return new Date(year, month - 1, 1).toLocaleDateString(undefined, { month: "long", year: "numeric" });
}

function reasonText(health, category) {
  const shortfall = health.projected_shortfall > 0 ? ` Projected to fall short by ${currency(health.projected_shortfall)}.` : "";
  if (health.reason === "goal_achieved") return "You've hit this goal.";
  if (health.reason === "ahead_of_pace") return "Saving faster than planned — nice.";
  if (health.reason === "on_pace") return "Right on pace.";
  if (health.reason === "general_overspend") return `Overall spending is eating into savings capacity.${shortfall}`;
  return `${category} spending is running over budget, eating into savings capacity.${shortfall}`;
}

function GoalCard({ goal, onChanged }) {
  const [contribution, setContribution] = useState("");
  const [busy, setBusy] = useState(false);

  const pct = Math.min(goal.target_amount > 0 ? goal.current_saved / goal.target_amount : 0, 1);
  const achieved = goal.health.reason === "goal_achieved";
  const token = achieved ? PACE_TOKEN.on_pace : PACE_TOKEN[goal.health.pace_status] ?? PACE_TOKEN.on_pace;

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
    <div className="border border-hairline bg-ground px-5 py-4">
      <div className="mb-1 flex items-baseline justify-between gap-3">
        <span className="font-display text-[15px] font-semibold text-ink">{goal.name}</span>
        <span
          className="border font-display text-[10px] font-semibold uppercase tracking-[.06em]"
          style={{ color: token.fg, background: token.bg, borderColor: token.br, padding: "3px 7px" }}
        >
          {achieved ? "Goal reached" : token.label}
        </span>
      </div>
      <div className="mb-2.5 flex items-baseline justify-between gap-3">
        <span className="num text-[13px] text-ink-muted">
          {currency(goal.current_saved)} / {currency(goal.target_amount)}
        </span>
        {goal.health.projected_completion_date && (
          <span className="text-[12px] text-ink-faint">est. {formatMonth(goal.health.projected_completion_date)}</span>
        )}
      </div>
      <span className="relative block h-2 bg-track">
        <span className="absolute inset-y-0 left-0" style={{ width: `${pct * 100}%`, background: token.fg }} />
      </span>
      <p className="mt-2.5 text-[12.5px] leading-[1.5] text-ink-faint">{reasonText(goal.health, goal.category)}</p>

      {!achieved && (
        <div className="mt-3 flex items-center gap-2">
          <input
            type="number"
            min="0"
            placeholder="Add contribution"
            value={contribution}
            onChange={(e) => setContribution(e.target.value)}
            className="h-9 w-full border border-field bg-surface px-2.5 text-[13px] text-ink outline-none focus:border-accent"
          />
          <button
            type="button"
            onClick={addContribution}
            disabled={busy}
            className="whitespace-nowrap border border-field px-3 py-2 font-display text-[11px] font-semibold uppercase tracking-[.05em] text-ink hover:bg-sunken disabled:opacity-50"
          >
            Add
          </button>
        </div>
      )}
      <button
        type="button"
        onClick={abandon}
        disabled={busy}
        className="mt-2.5 text-[11.5px] text-ink-faint underline decoration-dotted hover:text-crit"
      >
        Abandon goal
      </button>
    </div>
  );
}

export function GoalsSection({ goals, onChanged }) {
  return (
    <div>
      <h3 className="mb-4 font-display text-[16px] font-semibold uppercase tracking-[.07em] text-ink">Your goals</h3>
      {goals.length === 0 ? (
        <p className="text-[13.5px] text-ink-faint">
          No goals yet — when a purchase doesn't fit, you can track it as a goal from the result panel.
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {goals.map((g) => (
            <GoalCard key={g.id} goal={g} onChanged={onChanged} />
          ))}
        </div>
      )}
    </div>
  );
}
