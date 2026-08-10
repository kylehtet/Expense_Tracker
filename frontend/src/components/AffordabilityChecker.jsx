import { useState } from "react";
import { api } from "../api";
import { Corners } from "./Corners";
import { GoalsSection } from "./GoalsSection";

const CATEGORIES = ["Housing", "Food", "Transport", "Subscriptions", "Entertainment", "Other"];
const TIMINGS = [
  { value: "one_time", label: "One-time" },
  { value: "monthly", label: "Monthly" },
  { value: "split_3", label: "Split 3×" },
];

const VERDICT_TOKEN = {
  comfortable: { fg: "var(--good)", bg: "var(--good-bg)", br: "var(--good-br)", label: "Fits comfortably" },
  tight: { fg: "var(--warn)", bg: "var(--warn-bg)", br: "var(--warn-br)", label: "Tight — it fits, barely" },
  over: { fg: "var(--crit)", bg: "var(--crit-bg)", br: "var(--crit-br)", label: "Doesn't fit" },
};

const currency = (value) =>
  value == null ? "—" : `${value < 0 ? "−" : ""}$${Math.abs(value).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;

const CATEGORY_VAR = {
  Housing: "var(--cat-housing)",
  Food: "var(--cat-food)",
  Entertainment: "var(--cat-entertainment)",
  Transport: "var(--cat-transport)",
  Other: "var(--cat-other)",
  Subscriptions: "var(--cat-subs)",
};

export function AffordabilityChecker({ status, isSandbox, goals, onGoalsChanged }) {
  const [price, setPrice] = useState("100");
  const [category, setCategory] = useState("Entertainment");
  const [timing, setTiming] = useState("one_time");
  const [location, setLocation] = useState("");
  const [state, setState] = useState("idle"); // idle | loading | error
  const [errorMessage, setErrorMessage] = useState(null);
  const [result, setResult] = useState(null);
  const [recentChecks, setRecentChecks] = useState([]);
  const [tracking, setTracking] = useState("idle"); // idle | naming | saving | done
  const [goalName, setGoalName] = useState("");

  const checkIt = async () => {
    const amount = Number(price);
    if (!Number.isFinite(amount) || amount <= 0) {
      setState("error");
      setErrorMessage("Enter an amount greater than $0.");
      return;
    }
    setState("loading");
    setErrorMessage(null);
    setTracking("idle");
    try {
      const response = await api.checkAffordability(
        amount,
        category,
        timing,
        category === "Housing" ? location.trim() || undefined : undefined
      );
      setResult(response);
      setRecentChecks((prev) => [{ price: amount, category, timing, verdict: response.verdict }, ...prev].slice(0, 5));
      setState("idle");
    } catch (err) {
      setState("error");
      setErrorMessage(err.status === 429 ? err.message : "Something went wrong checking that. Try again.");
    }
  };

  const startTrackingGoal = () => {
    setGoalName(`${category} — ${currency(result.math.price)}`);
    setTracking("naming");
  };

  const saveGoal = async () => {
    if (!goalName.trim()) return;
    setTracking("saving");
    try {
      await api.createGoal({ name: goalName.trim(), targetAmount: result.math.price, category: result.math.category });
      await onGoalsChanged();
      setTracking("done");
    } catch {
      setTracking("naming");
    }
  };

  const rerunRecent = (check) => {
    setPrice(String(check.price));
    setCategory(check.category);
    setTiming(check.timing);
  };

  const budgetedCategories = Object.entries(status || {})
    .filter(([, v]) => v.budget != null)
    .map(([cat, v]) => ({ category: cat, left: v.remaining, budget: v.budget, actual: v.actual }))
    .sort((a, b) => a.left - b.left);

  const token = result ? VERDICT_TOKEN[result.verdict] ?? VERDICT_TOKEN.comfortable : null;
  const math = result?.math;

  const metrics = math
    ? [
        { label: `Left in ${math.category}`, value: currency(math.category_left_before), color: "var(--ink)" },
        {
          label: "After this purchase",
          value: currency(math.category_left_after),
          color: math.category_left_after == null || math.category_left_after >= 0 ? "var(--good)" : "var(--crit)",
        },
        {
          label: "Left across all budgets",
          value: currency(math.overall_left_after),
          color: math.overall_left_after >= 0 ? "var(--good)" : "var(--crit)",
        },
        { label: "Safe to spend today", value: currency(math.safe_to_spend_today), color: "var(--ink)" },
        { label: "Split over 3 months", value: `${currency(math.split_monthly)}/mo`, color: "var(--ink)" },
        {
          label: "Effect on pace",
          value: math.effect_on_pace_pct == null ? "—" : `${math.effect_on_pace_pct > 0 ? "+" : ""}${math.effect_on_pace_pct}%`,
          color: "var(--warn)",
        },
      ]
    : [];

  return (
    <div className="blueprint relative border border-hairline bg-ground">
      <Corners />
      <div
        className={
          isSandbox
            ? "flex items-center gap-2.5 border-b border-warn-br bg-warn-bg px-[26px] py-3 text-[13px] text-sandbox-text"
            : "flex items-center gap-2.5 border-b border-crit-br bg-crit-bg px-[26px] py-3 text-[13px] text-crit"
        }
      >
        <span className={`h-[7px] w-[7px] flex-none rounded-full ${isSandbox ? "bg-warn" : "bg-crit"}`} />
        <strong className="font-semibold">{isSandbox ? "Demo data" : "Live data"}</strong>
        <span>
          {isSandbox
            ? "Answers are computed from simulated Plaid data."
            : "Answers are computed from your real, connected bank data. Educational estimate only, not financial advice."}
        </span>
      </div>

      <div className="grid grid-cols-1 gap-px bg-rule lg:grid-cols-[420px_1fr]">
        <div className="bg-ground px-[30px] py-[30px]">
          <h3 className="m-0 mb-1.5 font-display text-[30px] font-semibold leading-[1.05] text-ink">
            Can I afford this?
          </h3>
          <p className="m-0 mb-6 text-[14px] leading-[1.6] text-ink-muted">
            Enter a purchase and we check it against what's left this month, your pace, and the
            category's own limit.
          </p>

          <label className="mb-2 block font-mono text-[10px] font-medium uppercase tracking-[.12em] text-ink-faint">
            Amount
          </label>
          <div className="mb-[22px] flex h-[58px] items-center gap-2.5 border border-field bg-surface px-4 focus-within:border-accent">
            <span className="font-mono text-[22px] text-ink-faint">$</span>
            <input
              type="number"
              min="0"
              step="1"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              className="num w-full border-0 bg-transparent text-[30px] font-medium text-ink outline-none"
            />
          </div>

          <label className="mb-2 block font-mono text-[10px] font-medium uppercase tracking-[.12em] text-ink-faint">
            Category
          </label>
          <div className="mb-[22px] flex flex-wrap gap-2">
            {CATEGORIES.map((c) => (
              <button
                key={c}
                type="button"
                onClick={() => setCategory(c)}
                aria-pressed={category === c}
                className="whitespace-nowrap border px-3.5 py-2.5 font-display text-[11.5px] font-semibold uppercase tracking-[.06em]"
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

          {category === "Housing" && (
            <>
              <label className="mb-2 block font-mono text-[10px] font-medium uppercase tracking-[.12em] text-ink-faint">
                Location <span className="normal-case text-ink-faint">(optional — city, state)</span>
              </label>
              <input
                type="text"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="e.g. Austin, TX"
                className="mb-[22px] h-[46px] w-full border border-field bg-surface px-3.5 text-[14px] text-ink outline-none focus:border-accent"
              />
            </>
          )}

          <label className="mb-2 block font-mono text-[10px] font-medium uppercase tracking-[.12em] text-ink-faint">
            Timing
          </label>
          <div className="mb-6 flex w-fit gap-px border border-field bg-field">
            {TIMINGS.map((t) => (
              <button
                key={t.value}
                type="button"
                onClick={() => setTiming(t.value)}
                aria-pressed={timing === t.value}
                className="whitespace-nowrap px-[18px] py-3 font-display text-[12.5px] font-semibold uppercase tracking-[.06em]"
                style={
                  timing === t.value
                    ? { background: "var(--accent-deep)", color: "var(--ground)" }
                    : { background: "var(--surface)", color: "var(--ink)" }
                }
              >
                {t.label}
              </button>
            ))}
          </div>

          <button
            onClick={checkIt}
            disabled={state === "loading"}
            className="blueprint relative inline-flex items-center bg-accent-deep px-6 py-3.5 font-display text-[15px] font-semibold uppercase tracking-[.05em] text-ground hover:bg-accent-press disabled:opacity-50"
          >
            <Corners />
            {state === "loading" ? "Checking…" : "Check it"}
          </button>
          {state === "error" && <p className="mt-3 text-[13px] text-crit">{errorMessage}</p>}
        </div>

        <div className="flex flex-col gap-6 bg-ground px-[30px] py-[30px]">
          {!result ? (
            <>
              <div>
                <h4 className="mb-1 font-display text-[13px] font-semibold uppercase tracking-[.06em] text-ink">
                  This month so far
                </h4>
                <p className="mb-4 text-[13px] text-ink-faint">
                  Fill in a purchase on the left and click "Check it" to see how it fits.
                </p>
                {budgetedCategories.length === 0 ? (
                  <p className="text-[13.5px] text-ink-faint">
                    No budgets set yet — set some in Settings to see them here.
                  </p>
                ) : (
                  <div className="flex flex-col">
                    {budgetedCategories.map((c) => (
                      <div
                        key={c.category}
                        className="grid grid-cols-[1fr_auto] items-center gap-3 border-t border-rule py-3"
                      >
                        <span className="flex items-center gap-2.5 text-[14px] text-ink">
                          <span
                            className="h-2.5 w-2.5 flex-none"
                            style={{ background: CATEGORY_VAR[c.category] ?? "var(--cat-other)" }}
                          />
                          {c.category}
                        </span>
                        <span
                          className="num text-[14px] font-medium"
                          style={{ color: c.left < 0 ? "var(--crit)" : "var(--ink)" }}
                        >
                          {currency(c.left)} left
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {recentChecks.length > 0 && (
                <div className="border-t border-rule pt-5">
                  <h4 className="mb-3 font-display text-[13px] font-semibold uppercase tracking-[.06em] text-ink">
                    Recent checks
                  </h4>
                  <div className="flex flex-col gap-2">
                    {recentChecks.map((c, i) => {
                      const t = VERDICT_TOKEN[c.verdict] ?? VERDICT_TOKEN.comfortable;
                      return (
                        <button
                          key={i}
                          type="button"
                          onClick={() => rerunRecent(c)}
                          className="flex items-center justify-between gap-3 border border-hairline px-3.5 py-2.5 text-left hover:bg-sunken"
                        >
                          <span className="text-[13.5px] text-ink">
                            {currency(c.price)} &middot; {c.category}
                          </span>
                          <span
                            className="border font-display text-[10px] font-semibold uppercase tracking-[.06em]"
                            style={{ color: t.fg, background: t.bg, borderColor: t.br, padding: "3px 7px" }}
                          >
                            {t.label}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </>
          ) : (
            <>
              <div
                className="blueprint relative border p-[22px_24px]"
                style={{ borderColor: token.br, background: token.bg }}
              >
                <Corners />
                <div
                  className="mb-2.5 font-mono text-[10px] font-medium uppercase tracking-[.14em]"
                  style={{ color: token.fg }}
                >
                  Verdict
                </div>
                <div
                  className="font-display text-[34px] font-semibold uppercase leading-[1.05]"
                  style={{ color: token.fg }}
                >
                  {token.label}
                </div>
                <p className="m-0 mt-2.5 max-w-[60ch] text-[14.5px] leading-[1.6]" style={{ color: token.fg }}>
                  {result.explanation}
                </p>
              </div>

              {result.verdict !== "comfortable" && result.savings_plan && (
                <div className="border border-hairline bg-sunken px-[22px] py-4">
                  {tracking === "done" ? (
                    <p className="m-0 text-[13.5px] text-ink">
                      Added to <strong>Your goals</strong> below — track your progress there.
                    </p>
                  ) : tracking === "naming" || tracking === "saving" ? (
                    <div className="flex flex-col gap-2.5 sm:flex-row sm:items-center">
                      <input
                        type="text"
                        value={goalName}
                        onChange={(e) => setGoalName(e.target.value)}
                        placeholder="Name this goal"
                        className="h-10 flex-1 border border-field bg-surface px-3 text-[13.5px] text-ink outline-none focus:border-accent"
                      />
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={saveGoal}
                          disabled={!goalName.trim() || tracking === "saving"}
                          className="whitespace-nowrap border border-accent bg-accent-tint px-3.5 py-2.5 font-display text-[11.5px] font-semibold uppercase tracking-[.05em] text-accent-deep disabled:opacity-50"
                        >
                          {tracking === "saving" ? "Saving…" : "Save goal"}
                        </button>
                        <button
                          type="button"
                          onClick={() => setTracking("idle")}
                          className="whitespace-nowrap px-3.5 py-2.5 font-display text-[11.5px] font-semibold uppercase tracking-[.05em] text-ink-faint"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <p className="m-0 text-[13.5px] text-ink-muted">
                        At {currency(result.savings_plan.monthly_savings_capacity)}/mo of budget headroom,{" "}
                        {result.savings_plan.months_to_goal == null
                          ? "this isn't reachable at your current pace."
                          : `you could save this in ~${result.savings_plan.months_to_goal} months.`}
                      </p>
                      <button
                        type="button"
                        onClick={startTrackingGoal}
                        className="whitespace-nowrap border border-field px-3.5 py-2.5 font-display text-[11.5px] font-semibold uppercase tracking-[.05em] text-ink hover:bg-sunken"
                      >
                        Track this as a goal
                      </button>
                    </div>
                  )}
                </div>
              )}

              <div className="grid grid-cols-1 gap-px border border-hairline bg-hairline sm:grid-cols-2">
                {metrics.map((m) => (
                  <div key={m.label} className="bg-ground px-[18px] py-4 pb-[18px]">
                    <div className="mb-2 font-mono text-[10px] font-medium uppercase tracking-[.1em] text-ink-faint">
                      {m.label}
                    </div>
                    <div className="num font-display text-[24px] font-semibold" style={{ color: m.color }}>
                      {m.value}
                    </div>
                  </div>
                ))}
              </div>

              {result.retrieved_facts?.length > 0 && (
                <div>
                  <div className="mb-2 font-mono text-[10px] font-medium uppercase tracking-[.12em] text-ink-faint">
                    Reference facts used
                  </div>
                  <ul className="flex flex-col gap-1.5">
                    {result.retrieved_facts.map((f, i) => (
                      <li key={i} className="text-[12.5px] leading-[1.5] text-ink-muted">
                        {f.text}{" "}
                        <span className="text-ink-faint">
                          — {f.source}
                          {f.stale ? " (cached)" : ""}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {recentChecks.length > 1 && (
                <div className="border-t border-rule pt-5">
                  <h4 className="mb-3 font-display text-[13px] font-semibold uppercase tracking-[.06em] text-ink">
                    Recent checks
                  </h4>
                  <div className="flex flex-col gap-2">
                    {recentChecks.slice(1).map((c, i) => {
                      const t = VERDICT_TOKEN[c.verdict] ?? VERDICT_TOKEN.comfortable;
                      return (
                        <button
                          key={i}
                          type="button"
                          onClick={() => rerunRecent(c)}
                          className="flex items-center justify-between gap-3 border border-hairline px-3.5 py-2.5 text-left hover:bg-sunken"
                        >
                          <span className="text-[13.5px] text-ink">
                            {currency(c.price)} &middot; {c.category}
                          </span>
                          <span
                            className="border font-display text-[10px] font-semibold uppercase tracking-[.06em]"
                            style={{ color: t.fg, background: t.bg, borderColor: t.br, padding: "3px 7px" }}
                          >
                            {t.label}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      <div className="border-t border-rule bg-ground px-[30px] py-[30px]">
        <GoalsSection goals={goals ?? []} onChanged={onGoalsChanged} />
      </div>
    </div>
  );
}
