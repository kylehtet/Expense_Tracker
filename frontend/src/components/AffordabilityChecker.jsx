import { useState } from "react";
import { api } from "../api";
import { Corners } from "./Corners";

const CATEGORIES = ["Housing", "Food", "Transport", "Shopping", "Subscriptions", "Entertainment", "Other"];

const TIMINGS = [
  { value: "one_time", label: "One-time purchase" },
  { value: "monthly", label: "New recurring monthly expense" },
  { value: "split_3", label: "Split across 3 months" },
];

const VERDICT_TOKEN = {
  comfortable: { fg: "var(--good)", bg: "var(--good-bg)", br: "var(--good-br)", label: "Yes — you can afford this." },
  tight: { fg: "var(--warn)", bg: "var(--warn-bg)", br: "var(--warn-br)", label: "It'll be tight." },
  over: { fg: "var(--crit)", bg: "var(--crit-bg)", br: "var(--crit-br)", label: "This would put you over." },
};

const currency = (value) =>
  value == null
    ? "—"
    : `${value < 0 ? "−" : ""}$${Math.abs(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export function AffordabilityChecker({ location, onGoalTracked }) {
  const [phase, setPhase] = useState("form"); // form | result
  const [item, setItem] = useState("");
  const [price, setPrice] = useState("");
  const [category, setCategory] = useState("Food");
  const [timing, setTiming] = useState("one_time");
  const [checkState, setCheckState] = useState("idle"); // idle | loading | error
  const [checkError, setCheckError] = useState(null);
  const [result, setResult] = useState(null);
  const [trackState, setTrackState] = useState("idle"); // idle | saving | done | error

  const handleSubmit = async (e) => {
    e.preventDefault();
    const amount = Number(price);
    if (!Number.isFinite(amount) || amount <= 0) {
      setCheckError("Enter a price greater than $0.");
      setCheckState("error");
      return;
    }
    setCheckState("loading");
    setCheckError(null);
    try {
      const response = await api.checkAffordability({ price: amount, category, timing, location });
      setResult(response);
      setTrackState("idle");
      setPhase("result");
      setCheckState("idle");
    } catch (err) {
      setCheckState("error");
      setCheckError(err.status === 429 ? "Give it a moment and try again." : "Couldn't run that check. Try again.");
    }
  };

  const startOver = () => {
    setPhase("form");
    setResult(null);
    setCheckState("idle");
    setCheckError(null);
  };

  const trackAsGoal = async () => {
    setTrackState("saving");
    try {
      await api.createGoal({
        name: item.trim() || `${category} purchase`,
        targetAmount: Number(price),
        category,
        currentSaved: 0,
      });
      await onGoalTracked?.();
      setTrackState("done");
    } catch {
      setTrackState("error");
    }
  };

  if (phase === "result" && result) {
    const token = VERDICT_TOKEN[result.verdict] ?? VERDICT_TOKEN.tight;
    const m = result.math;
    const facts = [
      { label: `${category} left this month`, value: currency(m.category_left_before) },
      { label: "This purchase", value: currency(Number(price)) },
      { label: `${category} left after this`, value: currency(m.category_left_after) },
      { label: "Overall left this month", value: currency(m.overall_left_before) },
      { label: "Safe to spend today", value: currency(m.safe_to_spend_today) },
      { label: "Days left in month", value: m.days_remaining },
      {
        label: "Effect on daily pace",
        value: m.effect_on_pace_pct == null ? "—" : `${m.effect_on_pace_pct > 0 ? "+" : ""}${m.effect_on_pace_pct}%`,
      },
    ];

    return (
      <div className="blueprint relative border border-hairline bg-ground">
        <Corners />
        <div className="grid grid-cols-1 gap-px bg-rule md:grid-cols-[1fr_1.2fr]">
          <div className="bg-ground px-7 py-[26px] pb-[30px]">
            <div className="mb-4 font-mono text-[10px] font-medium uppercase tracking-[.14em] text-ink-faint">
              Can I afford this?
            </div>
            <div className="flex flex-col gap-3.5">
              <div>
                <div className="mb-1 font-mono text-[10px] uppercase tracking-[.1em] text-ink-faint">Item</div>
                <div className="border border-field bg-surface px-3.5 py-2.5 text-[14px] text-ink">
                  {item.trim() || "—"}
                </div>
              </div>
              <div className="flex gap-3.5">
                <div className="flex-1">
                  <div className="mb-1 font-mono text-[10px] uppercase tracking-[.1em] text-ink-faint">Price</div>
                  <div className="num border border-field bg-surface px-3.5 py-2.5 text-[14px] text-ink">
                    {currency(Number(price))}
                  </div>
                </div>
                <div className="flex-1">
                  <div className="mb-1 font-mono text-[10px] uppercase tracking-[.1em] text-ink-faint">Category</div>
                  <div className="border border-field bg-surface px-3.5 py-2.5 text-[14px] text-ink">{category}</div>
                </div>
              </div>
            </div>

            <button
              type="button"
              onClick={startOver}
              className="mt-6 font-display text-[13px] font-semibold uppercase tracking-[.05em] text-accent-deep hover:text-accent-press"
            >
              &larr; Check something else
            </button>
          </div>

          <div className="bg-ground px-7 py-[26px] pb-[30px]">
            <div
              className="mb-4 inline-block border font-display text-[13px] font-bold uppercase tracking-[.05em]"
              style={{ color: token.fg, background: token.bg, borderColor: token.br, padding: "8px 14px" }}
            >
              {token.label}
            </div>
            <p className="m-0 mb-5 text-[14.5px] leading-[1.6] text-ink">{result.explanation}</p>
            <div className="flex flex-col">
              {facts.map((f) => (
                <div key={f.label} className="flex items-baseline justify-between gap-3 border-t border-rule py-2.5 text-[13px]">
                  <span className="text-ink-muted">{f.label}</span>
                  <span className="num font-medium text-ink">{f.value}</span>
                </div>
              ))}
            </div>

            {result.retrieved_facts.length > 0 && (
              <div className="mt-5">
                <div className="mb-2.5 font-display text-[12px] font-semibold uppercase tracking-[.06em] text-ink-faint">
                  Reference facts used
                </div>
                <ul className="flex flex-col gap-1.5">
                  {result.retrieved_facts.map((f) => (
                    <li key={f.text} className="text-[12.5px] leading-[1.5] text-ink-muted">
                      {f.text} {f.stale && <span className="text-warn">(cached)</span>}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {result.verdict !== "comfortable" && result.savings_plan && (
              <div className="mt-5 border border-hairline bg-surface px-4 py-3.5">
                {trackState === "done" ? (
                  <p className="m-0 text-[13.5px] font-medium text-good">
                    Tracking it as a goal — check your Dashboard.
                  </p>
                ) : (
                  <>
                    <p className="m-0 mb-3 text-[13.5px] leading-[1.6] text-ink">
                      Not there yet? At your current pace ({currency(result.savings_plan.monthly_savings_capacity)}
                      /mo headroom), this is about{" "}
                      <strong>
                        {result.savings_plan.months_to_goal == null
                          ? "not currently reachable"
                          : `${Math.ceil(result.savings_plan.months_to_goal)} month(s)`}
                      </strong>{" "}
                      away. Track it as a savings goal instead of spending now.
                    </p>
                    <button
                      type="button"
                      onClick={trackAsGoal}
                      disabled={trackState === "saving"}
                      className="whitespace-nowrap border border-accent-press bg-accent-deep px-4 py-2.5 font-display text-[12px] font-bold uppercase tracking-[.05em] text-ground disabled:opacity-50"
                    >
                      {trackState === "saving" ? "Saving…" : "Track this as a goal"}
                    </button>
                    {trackState === "error" && (
                      <p className="mt-2 text-[13px] text-crit">Couldn't save that goal. Try again.</p>
                    )}
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="blueprint relative mx-auto max-w-[480px] border border-hairline bg-ground">
      <Corners />
      <div className="px-[30px] py-10">
        <div className="mb-4 font-mono text-[10px] font-medium uppercase tracking-[.14em] text-ink-faint">
          Can I afford this?
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="mb-1.5 block font-mono text-[10px] font-medium uppercase tracking-[.1em] text-ink-faint">
              Item <span className="normal-case text-ink-faint">(optional)</span>
            </label>
            <input
              type="text"
              value={item}
              onChange={(e) => setItem(e.target.value)}
              placeholder="e.g. Concert tickets"
              className="h-[46px] w-full border border-field bg-surface px-3.5 text-[14px] text-ink outline-none focus:border-accent"
            />
          </div>
          <div className="flex gap-3.5">
            <div className="flex-1">
              <label className="mb-1.5 block font-mono text-[10px] font-medium uppercase tracking-[.1em] text-ink-faint">
                Price
              </label>
              <div className="flex h-[46px] items-center gap-1.5 border border-field bg-surface px-3.5 focus-within:border-accent">
                <span className="font-mono text-[14px] text-ink-faint">$</span>
                <input
                  type="number"
                  min="0"
                  step="1"
                  required
                  value={price}
                  onChange={(e) => setPrice(e.target.value)}
                  className="num w-full border-0 bg-transparent text-[14px] text-ink outline-none"
                />
              </div>
            </div>
            <div className="flex-1">
              <label className="mb-1.5 block font-mono text-[10px] font-medium uppercase tracking-[.1em] text-ink-faint">
                Timing
              </label>
              <select
                value={timing}
                onChange={(e) => setTiming(e.target.value)}
                className="h-[46px] w-full border border-field bg-surface px-3.5 text-[14px] text-ink outline-none focus:border-accent"
              >
                {TIMINGS.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div>
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
                  className="whitespace-nowrap border-2 px-3.5 py-2 font-display text-[11px] font-semibold uppercase tracking-[.05em]"
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

          {checkState === "error" && <p className="text-[13px] text-crit">{checkError}</p>}

          <button
            type="submit"
            disabled={checkState === "loading"}
            className="blueprint relative mt-1 inline-flex items-center justify-center bg-accent-deep px-6 py-3.5 font-display text-[15px] font-semibold uppercase tracking-[.05em] text-ground hover:bg-accent-press disabled:opacity-50"
          >
            <Corners />
            {checkState === "loading" ? "Checking…" : "Check"}
          </button>
        </form>
      </div>
    </div>
  );
}
