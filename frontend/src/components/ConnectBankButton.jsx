import { useCallback, useEffect, useState } from "react";
import { usePlaidLink } from "react-plaid-link";
import { api } from "../api";

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
    <div>
      <button
        onClick={() => open()}
        disabled={!ready || status === "linking"}
        className="rounded-md bg-[var(--series-housing)] px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
      >
        {status === "linking" ? "Connecting…" : "Connect your bank"}
      </button>
      {status === "error" && (
        <p className="mt-2 text-sm text-[var(--status-critical)]">
          Something went wrong connecting to Plaid. Try again.
        </p>
      )}
    </div>
  );
}
