import { useState } from "react";
import { api } from "../api";

const CATEGORIES = ["Housing", "Food", "Transport", "Subscriptions", "Entertainment", "Other"];

export function BudgetSettings({ userId, budgets, onSaved }) {
  const [drafts, setDrafts] = useState({});
  const [savingCategory, setSavingCategory] = useState(null);

  const valueFor = (category) => drafts[category] ?? budgets[category]?.budget ?? "";

  const save = async (category) => {
    const amount = Number(valueFor(category));
    if (!Number.isFinite(amount) || amount < 0) return;
    setSavingCategory(category);
    try {
      await api.setBudget(userId, category, amount);
      onSaved();
    } finally {
      setSavingCategory(null);
    }
  };

  return (
    <div className="flex flex-col gap-3">
      {CATEGORIES.map((category) => (
        <div key={category} className="flex items-center gap-3">
          <label htmlFor={`budget-${category}`} className="w-28 shrink-0 text-sm text-[var(--text-secondary)]">
            {category}
          </label>
          <span className="text-sm text-[var(--text-muted)]">$</span>
          <input
            id={`budget-${category}`}
            type="number"
            min="0"
            step="1"
            value={valueFor(category)}
            onChange={(e) => setDrafts((d) => ({ ...d, [category]: e.target.value }))}
            className="w-28 rounded border px-2 py-1 text-sm"
            style={{ borderColor: "var(--gridline)", background: "var(--surface-1)", color: "var(--text-primary)" }}
          />
          <button
            onClick={() => save(category)}
            disabled={savingCategory === category}
            className="rounded px-3 py-1 text-sm font-medium text-white disabled:opacity-50"
            style={{ background: "var(--series-housing)" }}
          >
            {savingCategory === category ? "Saving…" : "Save"}
          </button>
        </div>
      ))}
    </div>
  );
}
