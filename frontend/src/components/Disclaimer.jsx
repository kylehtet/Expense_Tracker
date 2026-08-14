export function Footer() {
  return (
    <div className="flex flex-col gap-1.5 border-t border-hairline bg-sunken px-[30px] py-2.5">
      <p className="m-0 max-w-[92ch] text-[11.5px] leading-[1.4] text-ink-muted">
        This is a personal project, not a bank or licensed financial service. Balances and
        budgets shown here are for information only.
      </p>
      <details>
        <summary className="cursor-pointer list-none font-display text-[11px] font-semibold uppercase tracking-[.06em] text-accent-deep">
          What data is stored, and where it goes &#8964;
        </summary>
        <p className="m-0 mt-2 max-w-[100ch] text-[12.5px] leading-[1.5] text-ink">
          Your bank's access token is encrypted before it's stored and is never sent back to this
          browser or logged. Transactions and the budgets you set are stored in this app's own
          database so your dashboard works between visits. Nothing here is sold, shared, or sent
          to any third party beyond Plaid (to read your transactions) and Anthropic (to write
          plain-language explanations and budget suggestions from your real numbers). Full{" "}
          <a href="/privacy" className="font-semibold text-accent-deep hover:text-accent-press">
            Privacy Policy
          </a>
          .
        </p>
      </details>
    </div>
  );
}
