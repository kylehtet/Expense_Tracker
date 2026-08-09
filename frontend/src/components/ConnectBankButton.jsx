import { useCallback, useEffect, useState } from "react";
import { usePlaidLink } from "react-plaid-link";
import { api } from "../api";
import { Corners } from "./Corners";

const POINTS = [
  "Read-only access through Plaid — transactions in, nothing out.",
  "Sorted into six fixed categories you can budget against.",
  "Your access token stays on your own server; budgets stay in your browser.",
];

export function ConnectBankButton({ userId, onLinked }) {
  const [linkToken, setLinkToken] = useState(null);
  const [status, setStatus] = useState("loading"); // loading | idle | linking | error

  useEffect(() => {
    let cancelled = false;
    api
      .createLinkToken(userId)
      .then(({ link_token }) => {
        if (!cancelled) {
          setLinkToken(link_token);
          setStatus("idle");
        }
      })
      .catch(() => !cancelled && setStatus("error"));
    return () => {
      cancelled = true;
    };
  }, [userId]);

  const onSuccess = useCallback(
    async (publicToken) => {
      setStatus("linking");
      try {
        await api.exchangePublicToken(userId, publicToken);
        onLinked();
        setStatus("idle");
      } catch {
        setStatus("error");
      }
    },
    [userId, onLinked]
  );

  const { open, ready } = usePlaidLink({ token: linkToken, onSuccess });

  return (
    <div className="blueprint relative border border-hairline bg-ground">
      <Corners />
      <div className="px-[30px] py-10">
        <div className="mb-3.5 font-mono text-[10px] font-medium uppercase tracking-[.14em] text-ink-faint">
          Step 1 of 2
        </div>
        <h1 className="mb-3 font-display text-[38px] font-semibold leading-[1.05] text-ink">
          Connect your bank
        </h1>
        <p className="mb-6 max-w-[46ch] text-[15px] leading-[1.6] text-ink">
          Expense Tracker reads your transactions through Plaid, sorts them into six categories
          and tracks them against budgets you set. Read-only — it can't move money.
        </p>
        <div className="mb-[30px] flex flex-col gap-[11px]">
          {POINTS.map((point) => (
            <div key={point} className="flex items-start gap-2.5 text-[14px] leading-[1.55] text-ink">
              <span className="relative mt-1 h-3.5 w-3.5 flex-none border border-accent">
                <span className="absolute inset-[3px] bg-accent-deep" />
              </span>
              <span>{point}</span>
            </div>
          ))}
        </div>
        <button
          onClick={() => open()}
          disabled={!ready || status === "linking"}
          className="blueprint relative inline-flex items-center bg-accent-deep px-6 py-3.5 font-display text-[15px] font-semibold uppercase tracking-[.05em] text-ground hover:bg-accent-press disabled:opacity-50"
        >
          <Corners />
          {status === "linking" ? "Connecting…" : "Launch Plaid Link"}
        </button>
        <p className="mt-4 text-[12.5px] text-ink-faint">
          Takes about 30 seconds. You can disconnect at any time from Settings.
        </p>
        {status === "error" && (
          <p className="mt-2 text-[13px] text-crit">
            Something went wrong connecting to Plaid. Try again.
          </p>
        )}
      </div>
    </div>
  );
}
