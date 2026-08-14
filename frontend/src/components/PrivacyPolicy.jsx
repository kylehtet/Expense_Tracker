import { Corners } from "./Corners";

const SECTIONS = [
  {
    title: "What this is",
    body: "Expense Tracker is a personal project, not a bank or a licensed financial service. It reads your transactions through Plaid, sorts them into categories, and helps you track budgets and goals. It cannot move money, initiate payments, or access anything beyond read-only transaction history.",
  },
  {
    title: "What's collected",
    body: "Your email and password are handled entirely by Firebase Authentication - this app never sees or stores your password. Once you connect a bank through Plaid, this app stores: an encrypted access token (used to sync transactions), your transaction history (merchant, amount, date, category), and any budgets or savings goals you set.",
  },
  {
    title: "Your bank login",
    body: "Handled directly by Plaid, never by this app. Plaid is a third-party service used by many banking and finance apps to connect accounts; your bank credentials are never sent to or stored by Expense Tracker.",
  },
  {
    title: "How it's stored",
    body: "The Plaid access token is encrypted before it's stored, using a key kept separately from the database itself. Transaction, budget, and goal data is stored in a database scoped to your account - other users cannot see it through the app. This data is not independently encrypted beyond the database provider's own storage-level protections.",
  },
  {
    title: "Who else sees it",
    body: "Plaid, to read your transactions on this app's behalf. Anthropic (Claude), only for the optional AI-written parts of the app - a plain-language explanation of an affordability check, a suggested budget number, or a suggested savings allocation - built from your real numbers, never given more data than needed for that one request. No analytics, no ad tech, no data broker, nobody else.",
  },
  {
    title: "Deleting your data",
    body: "Disconnecting your bank from Settings deletes the stored connection and your synced transactions immediately. This is a small, actively-developed project without a dedicated security team - reasonable care has gone into how it's built, but it hasn't been through a formal, professional security audit.",
  },
];

export function PrivacyPolicy() {
  return (
    <div className="flex min-h-screen flex-col items-center bg-ground px-6 py-16">
      <div className="w-full max-w-[680px]">
        <a
          href="/"
          className="mb-8 inline-block font-display text-[13px] font-semibold uppercase tracking-[.05em] text-ink-muted no-underline hover:text-accent-deep"
        >
          &larr; Back
        </a>
        <div className="blueprint relative border border-hairline bg-ground">
          <Corners />
          <div className="px-[34px] py-10">
            <h1 className="mb-2 font-display text-[30px] font-semibold leading-[1.1] text-ink">Privacy Policy</h1>
            <p className="mb-8 text-[13px] text-ink-faint">Last updated August 2026 · plain language, not legal boilerplate</p>

            <div className="flex flex-col gap-7">
              {SECTIONS.map((s) => (
                <section key={s.title}>
                  <h2 className="mb-2 font-display text-[15px] font-semibold uppercase tracking-[.04em] text-ink">
                    {s.title}
                  </h2>
                  <p className="m-0 text-[14.5px] leading-[1.65] text-ink">{s.body}</p>
                </section>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
