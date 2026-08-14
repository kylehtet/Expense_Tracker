import { useEffect, useState } from "react";
import { api } from "../api";
import { Corners } from "./Corners";

const LOAN_TERMS = [
  { value: "360", label: "30-year fixed" },
  { value: "180", label: "15-year fixed" },
];

const currency = (value) =>
  value == null
    ? "—"
    : `${value < 0 ? "−" : ""}$${Math.abs(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const pct = (decimal) => (decimal == null ? "—" : `${(decimal * 100).toFixed(1)}%`);

const cadenceLabel = (periodsPerYear) =>
  periodsPerYear === 52 ? "weekly" : periodsPerYear === 26 ? "biweekly" : "monthly";

function RatioBar({ label, ratio, limit }) {
  const over = ratio > limit;
  const fillPct = Math.min((ratio / limit) * 100, 130);
  const color = over ? "var(--crit)" : "var(--good)";
  return (
    <div className="mb-4">
      <div className="mb-1.5 flex items-baseline justify-between text-[13px]">
        <span className="text-ink-muted">{label}</span>
        <span className="num font-medium" style={{ color }}>
          {pct(ratio)} <span className="text-ink-faint">/ {pct(limit)} limit</span>
        </span>
      </div>
      <div className="relative h-2 border border-hairline bg-sunken">
        <div className="h-full" style={{ width: `${Math.min(fillPct, 100)}%`, background: color }} />
        <div className="absolute inset-y-0" style={{ left: `${100 / 1.3}%`, borderLeft: "2px dashed var(--ink-faint)" }} />
      </div>
    </div>
  );
}

export function HomePurchaseChecker({ location, onBack }) {
  const [phase, setPhase] = useState("form"); // form | result
  const [price, setPrice] = useState("");
  const [downPayment, setDownPayment] = useState("");
  const [loanTerm, setLoanTerm] = useState("360");
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [interestRatePct, setInterestRatePct] = useState("");
  const [propertyTaxRatePct, setPropertyTaxRatePct] = useState("");
  const [annualInsurance, setAnnualInsurance] = useState("");
  const [charges, setCharges] = useState([]);
  const [selectedDebts, setSelectedDebts] = useState(new Set());
  const [checkState, setCheckState] = useState("idle"); // idle | loading | error
  const [checkError, setCheckError] = useState(null);
  const [result, setResult] = useState(null);

  useEffect(() => {
    api.getRecurring().then(setCharges).catch(() => setCharges([]));
  }, []);

  const toggleDebt = (merchant) => {
    setSelectedDebts((prev) => {
      const next = new Set(prev);
      next.has(merchant) ? next.delete(merchant) : next.add(merchant);
      return next;
    });
  };

  const otherMonthlyDebts = charges
    .filter((c) => selectedDebts.has(c.merchant))
    .reduce((sum, c) => sum + c.average_amount, 0);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const amount = Number(price);
    const down = Number(downPayment);
    if (!Number.isFinite(amount) || amount <= 0) {
      setCheckError("Enter a home price greater than $0.");
      setCheckState("error");
      return;
    }
    if (!Number.isFinite(down) || down < 0 || down > amount) {
      setCheckError("Down payment must be between $0 and the home price.");
      setCheckState("error");
      return;
    }
    setCheckState("loading");
    setCheckError(null);
    try {
      const response = await api.checkHomeAffordability({
        price: amount,
        downPayment: down,
        loanTermMonths: Number(loanTerm),
        interestRate: interestRatePct ? Number(interestRatePct) / 100 : undefined,
        propertyTaxRate: propertyTaxRatePct ? Number(propertyTaxRatePct) / 100 : undefined,
        annualInsuranceEstimate: annualInsurance ? Number(annualInsurance) : undefined,
        otherMonthlyDebts,
        location,
      });
      setResult(response);
      setPhase("result");
      setCheckState("idle");
    } catch (err) {
      setCheckState("error");
      setCheckError(
        err.status === 429
          ? "Give it a moment and try again."
          : err.message || "Couldn't run that check. Try again."
      );
    }
  };

  const startOver = () => {
    setPhase("form");
    setResult(null);
    setCheckState("idle");
    setCheckError(null);
  };

  if (phase === "result" && result) {
    return (
      <div className="blueprint relative mx-auto max-w-[640px] border border-hairline bg-ground">
        <Corners />
        <div className="px-7 py-[26px] pb-[30px]">
          <button
            type="button"
            onClick={onBack}
            className="mb-4 font-display text-[11px] font-semibold uppercase tracking-[.05em] text-ink-faint hover:text-ink"
          >
            &larr; Back to quick check
          </button>

          <div className="mb-4 font-mono text-[10px] font-medium uppercase tracking-[.14em] text-ink-faint">
            {currency(Number(price))} home &middot; {currency(Number(downPayment))} down
          </div>
          <div
            className="mb-5 inline-block border font-display text-[13px] font-bold uppercase tracking-[.05em]"
            style={
              result.affordable
                ? { color: "var(--good)", background: "var(--good-bg)", borderColor: "var(--good-br)", padding: "8px 14px" }
                : { color: "var(--crit)", background: "var(--crit-bg)", borderColor: "var(--crit-br)", padding: "8px 14px" }
            }
          >
            {result.affordable ? "Within the 28/36 guideline" : "Over the 28/36 guideline"}
          </div>

          <RatioBar label="Housing payment / income (front-end)" ratio={result.front_end_ratio} limit={result.front_end_limit} />
          <RatioBar label="Total debt / income (back-end, DTI)" ratio={result.dti_ratio} limit={result.back_end_limit} />

          <div className="mb-6 mt-5 grid grid-cols-1 gap-px border border-hairline bg-rule sm:grid-cols-2">
            <div className="bg-ground px-5 py-4">
              <div className="mb-1 font-mono text-[10px] uppercase tracking-[.1em] text-ink-faint">Max affordable price</div>
              <div className="num text-[19px] font-semibold text-ink">{currency(result.max_affordable_price)}</div>
            </div>
            <div className="bg-ground px-5 py-4">
              <div className="mb-1 font-mono text-[10px] uppercase tracking-[.1em] text-ink-faint">Monthly payment (est.)</div>
              <div className="num text-[19px] font-semibold text-ink">{currency(result.monthly_payment_estimate)}</div>
              <div className="num mt-0.5 text-[12px] text-ink-muted">
                {currency(result.monthly_principal_interest)} P&amp;I + {currency(result.monthly_property_tax)} tax +{" "}
                {currency(result.monthly_insurance)} ins.
              </div>
            </div>
          </div>

          <div className="mb-5">
            <div className="mb-2.5 font-display text-[12px] font-semibold uppercase tracking-[.06em] text-ink-faint">
              Your income, from real synced transactions
            </div>
            <div className="flex flex-col">
              {result.income_sources.map((s) => (
                <div key={s.source} className="flex items-baseline justify-between gap-3 border-t border-rule py-2 text-[13px]">
                  <span className="text-ink-muted">
                    {s.source} <span className="text-ink-faint">({cadenceLabel(s.periods_per_year)})</span>
                  </span>
                  <span className="num font-medium text-ink">{currency(s.estimated_annual)}/yr</span>
                </div>
              ))}
              <div className="flex items-baseline justify-between gap-3 border-t border-rule py-2 text-[13px] font-semibold">
                <span className="text-ink">Estimated annual income</span>
                <span className="num text-ink">{currency(result.estimated_annual_income)}</span>
              </div>
              {result.other_monthly_debts > 0 && (
                <div className="flex items-baseline justify-between gap-3 border-t border-rule py-2 text-[13px]">
                  <span className="text-ink-muted">Other monthly debts (selected)</span>
                  <span className="num font-medium text-ink">{currency(result.other_monthly_debts)}/mo</span>
                </div>
              )}
            </div>
          </div>

          <div className="mb-5 text-[12.5px] text-ink-faint">
            Used {pct(result.interest_rate_used)} rate, {pct(result.property_tax_rate_used)} property tax,{" "}
            {currency(result.annual_insurance_estimate_used)}/yr insurance
            {" "}— current market data unless you overrode a field above.
          </div>

          {result.retrieved_facts.length > 0 && (
            <div className="mb-2">
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

          <button
            type="button"
            onClick={startOver}
            className="mt-4 font-display text-[13px] font-semibold uppercase tracking-[.05em] text-accent-deep hover:text-accent-press"
          >
            &larr; Check a different home
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="blueprint relative mx-auto max-w-[480px] border border-hairline bg-ground">
      <Corners />
      <div className="px-[30px] py-10">
        <button
          type="button"
          onClick={onBack}
          className="mb-4 font-display text-[11px] font-semibold uppercase tracking-[.05em] text-ink-faint hover:text-ink"
        >
          &larr; Back to quick check
        </button>

        <div className="mb-1.5 font-mono text-[10px] font-medium uppercase tracking-[.14em] text-ink-faint">
          Buying a home?
        </div>
        <p className="mb-5 text-[13px] leading-[1.5] text-ink-muted">
          A 28/36 debt-to-income check, using income detected from your real recurring deposits — not typed in.
        </p>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex gap-3.5">
            <div className="flex-1">
              <label className="mb-1.5 block font-mono text-[10px] font-medium uppercase tracking-[.1em] text-ink-faint">
                Home price
              </label>
              <div className="flex h-[46px] items-center gap-1.5 border border-field bg-surface px-3.5 focus-within:border-accent">
                <span className="font-mono text-[14px] text-ink-faint">$</span>
                <input
                  type="number"
                  min="0"
                  step="1000"
                  required
                  value={price}
                  onChange={(e) => setPrice(e.target.value)}
                  className="num w-full border-0 bg-transparent text-[14px] text-ink outline-none"
                />
              </div>
            </div>
            <div className="flex-1">
              <label className="mb-1.5 block font-mono text-[10px] font-medium uppercase tracking-[.1em] text-ink-faint">
                Down payment
              </label>
              <div className="flex h-[46px] items-center gap-1.5 border border-field bg-surface px-3.5 focus-within:border-accent">
                <span className="font-mono text-[14px] text-ink-faint">$</span>
                <input
                  type="number"
                  min="0"
                  step="1000"
                  required
                  value={downPayment}
                  onChange={(e) => setDownPayment(e.target.value)}
                  className="num w-full border-0 bg-transparent text-[14px] text-ink outline-none"
                />
              </div>
            </div>
          </div>

          <div>
            <label className="mb-1.5 block font-mono text-[10px] font-medium uppercase tracking-[.1em] text-ink-faint">
              Loan term
            </label>
            <div className="flex flex-wrap gap-2">
              {LOAN_TERMS.map((t) => (
                <button
                  key={t.value}
                  type="button"
                  onClick={() => setLoanTerm(t.value)}
                  aria-pressed={loanTerm === t.value}
                  className="whitespace-nowrap border-2 px-3.5 py-2 font-display text-[11px] font-semibold uppercase tracking-[.05em]"
                  style={
                    loanTerm === t.value
                      ? { borderColor: "var(--accent)", background: "var(--accent-tint)", color: "var(--accent-deep)" }
                      : { borderColor: "var(--field)", background: "transparent", color: "var(--ink)" }
                  }
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          {charges.length > 0 && (
            <div>
              <label className="mb-1.5 block font-mono text-[10px] font-medium uppercase tracking-[.1em] text-ink-faint">
                Which of these are debt obligations? <span className="normal-case text-ink-faint">(optional)</span>
              </label>
              <div className="flex flex-col gap-1.5 border border-field bg-surface px-3.5 py-3">
                {charges.map((c) => (
                  <label key={c.merchant} className="flex cursor-pointer items-center justify-between gap-3 text-[13px]">
                    <span className="flex items-center gap-2 text-ink">
                      <input
                        type="checkbox"
                        checked={selectedDebts.has(c.merchant)}
                        onChange={() => toggleDebt(c.merchant)}
                      />
                      {c.merchant}
                    </span>
                    <span className="num text-ink-muted">{currency(c.average_amount)}/mo</span>
                  </label>
                ))}
              </div>
            </div>
          )}

          <button
            type="button"
            onClick={() => setAdvancedOpen((o) => !o)}
            className="text-left font-display text-[11px] font-semibold uppercase tracking-[.05em] text-accent-deep hover:text-accent-press"
          >
            {advancedOpen ? "Hide advanced" : "Advanced: override rate / tax / insurance"}
          </button>

          {advancedOpen && (
            <div className="flex flex-col gap-3.5 border border-hairline bg-surface px-3.5 py-3.5">
              <div>
                <label className="mb-1.5 block font-mono text-[10px] font-medium uppercase tracking-[.1em] text-ink-faint">
                  Interest rate % <span className="normal-case text-ink-faint">(blank = current market rate)</span>
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={interestRatePct}
                  onChange={(e) => setInterestRatePct(e.target.value)}
                  className="h-[40px] w-full border border-field bg-ground px-3 text-[13.5px] text-ink outline-none focus:border-accent"
                />
              </div>
              <div>
                <label className="mb-1.5 block font-mono text-[10px] font-medium uppercase tracking-[.1em] text-ink-faint">
                  Property tax rate % <span className="normal-case text-ink-faint">(blank = state average)</span>
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={propertyTaxRatePct}
                  onChange={(e) => setPropertyTaxRatePct(e.target.value)}
                  className="h-[40px] w-full border border-field bg-ground px-3 text-[13.5px] text-ink outline-none focus:border-accent"
                />
              </div>
              <div>
                <label className="mb-1.5 block font-mono text-[10px] font-medium uppercase tracking-[.1em] text-ink-faint">
                  Annual insurance $ <span className="normal-case text-ink-faint">(blank = state average)</span>
                </label>
                <input
                  type="number"
                  step="50"
                  value={annualInsurance}
                  onChange={(e) => setAnnualInsurance(e.target.value)}
                  className="h-[40px] w-full border border-field bg-ground px-3 text-[13.5px] text-ink outline-none focus:border-accent"
                />
              </div>
            </div>
          )}

          {checkState === "error" && <p className="text-[13px] text-crit">{checkError}</p>}

          <button
            type="submit"
            disabled={checkState === "loading"}
            className="blueprint relative mt-1 inline-flex items-center justify-center bg-accent-deep px-6 py-3.5 font-display text-[15px] font-semibold uppercase tracking-[.05em] text-ground hover:bg-accent-press disabled:opacity-50"
          >
            <Corners />
            {checkState === "loading" ? "Checking…" : "Check affordability"}
          </button>
        </form>
      </div>
    </div>
  );
}
