export function Footer() {
  return (
    <div className="flex flex-col gap-2.5 border-t border-hairline bg-sunken px-[30px] py-[18px]">
      <p className="m-0 max-w-[92ch] text-[12.5px] leading-[1.5] text-ink-muted">
        This is a personal project, not a bank or licensed financial service. Balances and
        budgets shown here are for information only.
      </p>
      <details>
        <summary className="cursor-pointer list-none font-display text-[12px] font-semibold uppercase tracking-[.06em] text-accent-deep">
          What data is stored, and where it goes &#8964;
        </summary>
        <p className="m-0 mt-2.5 max-w-[100ch] text-[13px] leading-[1.6] text-ink">
          Your bank's access token is encrypted before it's stored and is never sent back to this
          browser or logged. Transactions and the budgets you set are stored in this app's own
          database so your dashboard works between visits. Nothing here is sold, shared, or sent
          to any third party beyond Plaid (to read your transactions) and, if you use the
          affordability checker, Anthropic (to parse your question and write the explanation).
        </p>
      </details>
    </div>
  );
}
