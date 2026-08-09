import { useState } from "react";
import { api } from "../api";
import { Corners } from "./Corners";

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

export function AffordabilityChecker({ userId, isSandbox }) {
  const [price, setPrice] = useState("100");
  const [category, setCategory] = useState("Entertainment");
  const [timing, setTiming] = useState("one_time");
  const [state, setState] = useState("idle"); // idle | loading | error
  const [errorMessage, setErrorMessage] = useState(null);
  const [result, setResult] = useState(null);

  const checkIt = async () => {
    const amount = Number(price);
    if (!Number.isFinite(amount) || amount <= 0) {
      setState("error");
      setErrorMessage("Enter an amount greater than $0.");
      return;
    }
    setState("loading");
    setErrorMessage(null);
    try {
      const response = await api.checkAffordability(userId, amount, category, timing);
      setResult(response);
      setState("idle");
    } catch (err) {
      setState("error");
      setErrorMessage(err.status === 429 ? err.message : "Something went wrong checking that. Try again.");
    }
  };

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
      <div className="flex items-center gap-2.5 border-b border-warn-br bg-warn-bg px-[26px] py-3 text-[13px] text-sandbox-text">
        <span className="h-[7px] w-[7px] flex-none rounded-full bg-warn" />
        <strong className="font-semibold">Demo mode</strong>
        <span>{isSandbox ? "Answers are computed from simulated Plaid data." : "Educational estimate only, not financial advice."}</span>
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
            <p className="text-[14px] text-ink-faint">
              Fill in a purchase and click "Check it" to see how it fits your budget.
            </p>
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
            </>
          )}
        </div>
      </div>
    </div>
  );
}
