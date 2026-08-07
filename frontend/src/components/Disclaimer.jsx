export function Disclaimer() {
  return (
    <p className="text-xs leading-relaxed text-[var(--text-muted)]">
      This is a personal project, not a bank or licensed financial service. Use
      at your own discretion. Educational estimate only, not financial advice.
    </p>
  );
}

export function PrivacyNote() {
  return (
    <details className="text-xs text-[var(--text-muted)]">
      <summary className="cursor-pointer select-none text-[var(--text-secondary)]">
        What data is stored, and where it goes
      </summary>
      <p className="mt-2 leading-relaxed">
        Your bank's access token is encrypted before it's stored and is never
        sent back to this browser or logged. Transactions and the budgets you
        set are stored locally in this app's own database so your dashboard
        works between visits. Nothing here is sold, shared, or sent to any
        third party beyond Plaid (to read your transactions) and, if you use
        the affordability checker, Anthropic (to parse your question and
        write the explanation).
      </p>
    </details>
  );
}
