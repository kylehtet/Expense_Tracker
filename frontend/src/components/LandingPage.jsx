import { useState } from "react";
import { signInWithEmailAndPassword } from "firebase/auth";
import { auth } from "../firebase";
import { Corners } from "./Corners";
import { InterestForm } from "./InterestForm";

const GITHUB_URL = "https://github.com/kylehtet/can_u_afford_it";

// A shared, pre-seeded account anyone can view without connecting a real
// bank themselves - read-only server-side (see app.main.DEMO_UID), so it's
// safe to sign into from here with no gate. Not a secret; the whole point is
// that visitors can use it.
const DEMO_EMAIL = "demo@expensetracker.tech";
const DEMO_PASSWORD = "TryTheDemo2026!";

const NAV_LINKS = [
  { href: "#how", label: "How it works" },
  { href: "#privacy", label: "Your data" },
];

// Demo data for the dashboard preview - illustrative only, not live figures.
const PREVIEW_CATS = [
  { name: "Housing", spent: 1450, budget: 1500, hue: "var(--cat-housing)" },
  { name: "Food", spent: 612, budget: 700, hue: "var(--cat-food)" },
  { name: "Entertainment", spent: 402, budget: 500, hue: "var(--cat-entertainment)" },
  { name: "Transport", spent: 318, budget: 400, hue: "var(--cat-transport)" },
  { name: "Shopping", spent: 289, budget: 350, hue: "var(--cat-shopping)" },
  { name: "Other", spent: 268, budget: 900, hue: "var(--cat-other)" },
  { name: "Subscriptions", spent: 164, budget: 150, hue: "var(--cat-subs)" },
];
const PACE = 0.74;
const PREVIEW_TOTAL = PREVIEW_CATS.reduce((sum, c) => sum + c.spent, 0);
const PREVIEW_MAX = Math.max(...PREVIEW_CATS.map((c) => c.spent));
const PREVIEW_BUDGET = PREVIEW_CATS.reduce((sum, c) => sum + c.budget, 0);

const STATUS_TOKEN = {
  under: { fg: "var(--good)", bg: "var(--good-bg)", br: "var(--good-br)", label: "Under" },
  on_track: { fg: "var(--warn)", bg: "var(--warn-bg)", br: "var(--warn-br)", label: "On track" },
  over: { fg: "var(--crit)", bg: "var(--crit-bg)", br: "var(--crit-br)", label: "Over" },
};

function previewStatus(spent, budget) {
  const ratio = spent / budget;
  if (ratio > 1) return STATUS_TOKEN.over;
  if (ratio > PACE) return STATUS_TOKEN.on_track;
  return STATUS_TOKEN.under;
}

const STEPS = [
  {
    num: "01",
    title: "Connect a bank",
    body: "Plaid Link handles the login. Access is read-only: the app can see transactions and balances, and it cannot move money.",
    tag: "Working",
  },
  {
    num: "02",
    title: "Sort into seven categories",
    body: "Housing, Food, Transport, Shopping, Subscriptions, Entertainment, Other. Fixed on purpose — seven buckets you will actually keep up with beat forty you abandon.",
    tag: "Working",
  },
  {
    num: "03",
    title: "Set a budget, watch the pace",
    body: "A monthly limit per category, with a marker for where you should be by today's date. Under, on track and over are the only three states.",
    tag: "Working",
  },
  {
    num: "04",
    title: "Check what you can afford",
    body: "Enter a purchase and see what it does to the month before you make it, not after — the numbers are pure arithmetic on your real budgets; an LLM only writes the plain-language explanation.",
    tag: "Working",
  },
];

// Illustrative example of the affordability check - a real check does the same
// deterministic budget-headroom math against your actual synced spending; an
// LLM only ever writes the one-sentence explanation on top of that math, never
// the verdict itself. Numbers here are made up for the example.
const AFFORDABILITY_EXAMPLE = {
  item: "Concert tickets",
  price: 180,
  category: "Entertainment",
  headline: "Yes — you can afford this.",
  explanation:
    "Entertainment has $312 left this month, and this wouldn't push Food or Housing over pace either.",
  facts: [
    { label: "Entertainment left this month", value: "$312.00" },
    { label: "This purchase", value: "$180.00" },
    { label: "Days left in month", value: "17" },
  ],
};

// Same real feature, same made-up-for-illustration numbers as the rest of
// this preview - goal pace is computed the same deterministic way as the
// budget math above, an LLM never decides whether a goal is on track.
const GOALS_EXAMPLE = [
  { name: "Flight to Tokyo", saved: 890, target: 1800, status: "on_track" },
  { name: "New laptop", saved: 240, target: 1200, status: "behind" },
];

const GOAL_STATUS_TOKEN = {
  on_track: { fg: "var(--good)", bg: "var(--good-bg)", label: "On track" },
  behind: { fg: "var(--crit)", bg: "var(--crit-bg)", label: "Behind pace" },
};

const PRIVACY = [
  {
    label: "In this app's database",
    title: "Budgets and synced transactions",
    body: "Budgets and categorized transactions are stored server-side so your dashboard works between visits, encrypted at rest where it matters.",
  },
  {
    label: "On the server, encrypted",
    title: "The Plaid access token",
    body: "Your bank's access token is encrypted before storage and never sent back to the browser or logged. It's never in a URL, a log line, or an API response.",
  },
  {
    label: "Nowhere",
    title: "Analytics, tracking, ad tech",
    body: "No analytics, no tracking pixels, no third-party scripts on this page or in the app beyond Plaid itself. The source is public — check it.",
  },
];

function LogoMark() {
  return (
    <span className="relative block h-[18px] w-[18px] border-[1.5px] border-accent-deep">
      <span className="absolute bottom-0.5 left-0.5 h-[5px] w-[3px] bg-accent-deep" />
      <span className="absolute bottom-0.5 left-[7.5px] h-[11px] w-[3px] bg-accent-deep" />
      <span className="absolute bottom-0.5 left-[13px] h-[8px] w-[3px] bg-accent-deep" />
    </span>
  );
}

function DashboardPreview() {
  return (
    <div className="blueprint relative border border-hairline bg-ground">
      <Corners />
      <div className="flex items-center gap-2.5 border-b border-warn-br bg-warn-bg px-[26px] py-[11px] text-[13px] text-sandbox-text">
        <span className="h-[7px] w-[7px] flex-none rounded-full bg-warn" />
        <strong className="font-semibold">Demo mode</strong>
        <span>simulated bank data — the sandbox indicator is always visible</span>
      </div>
      <div className="grid grid-cols-1 gap-px bg-rule md:grid-cols-[1.25fr_1fr]">
        <div className="bg-ground px-7 py-[26px] pb-[30px]">
          <div className="mb-2.5 font-mono text-[10px] font-medium uppercase tracking-[.14em] text-ink-faint">
            August 2026 &middot; to date
          </div>
          <div className="mb-[26px] flex items-baseline gap-3.5">
            <span className="num font-display text-[42px] font-semibold text-ink">
              ${PREVIEW_TOTAL.toLocaleString()}
            </span>
            <span className="text-[14px] text-ink-muted">of ${PREVIEW_BUDGET.toLocaleString()} budgeted</span>
          </div>
          <div className="flex flex-col gap-[13px]">
            {PREVIEW_CATS.map((c) => (
              <div key={c.name} className="grid grid-cols-[104px_1fr_82px] items-center gap-[13px]">
                <span className="truncate text-[13.5px] text-ink">{c.name}</span>
                <span className="relative block h-[18px] bg-track">
                  <span
                    className="absolute inset-y-0 left-0 bg-accent"
                    style={{ width: `${(c.spent / PREVIEW_MAX) * 100}%` }}
                  />
                </span>
                <span className="num text-right text-[13.5px] font-medium text-ink">
                  ${c.spent.toLocaleString()}
                </span>
              </div>
            ))}
          </div>
          <div className="mt-6 flex h-[22px] w-full border border-hairline">
            {PREVIEW_CATS.map((c) => (
              <span
                key={c.name}
                className="block"
                style={{ width: `${(c.spent / PREVIEW_TOTAL) * 100}%`, background: c.hue }}
              />
            ))}
          </div>
        </div>
        <div className="bg-ground px-7 py-[26px] pb-[30px]">
          <div className="mb-3.5 font-display text-[15px] font-semibold uppercase tracking-[.07em] text-ink">
            Budget progress
          </div>
          <div className="flex flex-col">
            {PREVIEW_CATS.map((c) => {
              const token = previewStatus(c.spent, c.budget);
              const pct = Math.min(c.spent / c.budget, 1);
              return (
                <div key={c.name} className="flex flex-col gap-2 border-t border-rule py-[13px]">
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="text-[14px] text-ink">{c.name}</span>
                    <span
                      className="border font-display text-[10.5px] font-semibold uppercase tracking-[.08em]"
                      style={{ color: token.fg, background: token.bg, borderColor: token.br, padding: "5px 8px" }}
                    >
                      {token.label}
                    </span>
                  </div>
                  <span className="relative block h-[7px] bg-track">
                    <span
                      className="absolute inset-y-0 left-0"
                      style={{ width: `${pct * 100}%`, background: token.fg }}
                    />
                    <span
                      className="absolute -inset-y-[3px] w-px bg-ink opacity-45"
                      style={{ left: `${PACE * 100}%` }}
                    />
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
      <div className="border-t border-hairline bg-ground px-7 py-[26px] pb-[30px]">
        <div className="mb-3.5 font-display text-[15px] font-semibold uppercase tracking-[.07em] text-ink">
          Your goals
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {GOALS_EXAMPLE.map((g) => {
            const token = GOAL_STATUS_TOKEN[g.status];
            const pct = Math.min(g.saved / g.target, 1);
            return (
              <div key={g.name} className="border border-hairline px-5 py-4">
                <div className="mb-1.5 flex items-baseline justify-between gap-3">
                  <span className="font-display text-[14.5px] font-semibold text-ink">{g.name}</span>
                  <span
                    className="flex-none font-display text-[10px] font-bold uppercase tracking-[.05em]"
                    style={{ color: token.fg, background: token.bg, padding: "3px 8px" }}
                  >
                    {token.label}
                  </span>
                </div>
                <span className="num text-[13px] text-ink-muted">
                  ${g.saved.toLocaleString()} / ${g.target.toLocaleString()}
                </span>
                <span className="relative mt-2 block h-2 bg-track">
                  <span className="absolute inset-y-0 left-0" style={{ width: `${pct * 100}%`, background: token.fg }} />
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function AffordabilityExample() {
  const ex = AFFORDABILITY_EXAMPLE;
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
              <div className="border border-field bg-surface px-3.5 py-2.5 text-[14px] text-ink">{ex.item}</div>
            </div>
            <div className="flex gap-3.5">
              <div className="flex-1">
                <div className="mb-1 font-mono text-[10px] uppercase tracking-[.1em] text-ink-faint">Price</div>
                <div className="num border border-field bg-surface px-3.5 py-2.5 text-[14px] text-ink">
                  ${ex.price.toLocaleString()}
                </div>
              </div>
              <div className="flex-1">
                <div className="mb-1 font-mono text-[10px] uppercase tracking-[.1em] text-ink-faint">Category</div>
                <div className="border border-field bg-surface px-3.5 py-2.5 text-[14px] text-ink">{ex.category}</div>
              </div>
            </div>
          </div>
        </div>
        <div className="bg-ground px-7 py-[26px] pb-[30px]">
          <div
            className="mb-4 inline-block border font-display text-[13px] font-bold uppercase tracking-[.05em]"
            style={{ color: "var(--good)", background: "var(--good-bg)", borderColor: "var(--good-br)", padding: "8px 14px" }}
          >
            {ex.headline}
          </div>
          <p className="m-0 mb-5 text-[14.5px] leading-[1.6] text-ink">{ex.explanation}</p>
          <div className="flex flex-col">
            {ex.facts.map((f) => (
              <div key={f.label} className="flex items-baseline justify-between gap-3 border-t border-rule py-2.5 text-[13px]">
                <span className="text-ink-muted">{f.label}</span>
                <span className="num font-medium text-ink">{f.value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function HowItWorksSheet() {
  return (
    <div className="blueprint relative border border-hairline">
      <Corners />
      <div className="flex flex-wrap items-stretch border-b border-hairline font-display text-[12.5px] font-semibold uppercase tracking-[.08em]">
        <span className="min-w-[16ch] flex-1 px-6 py-3">Expense Tracker — personal finance, synced from your bank</span>
        <span className="whitespace-nowrap border-l border-hairline px-6 py-3 text-ink-muted">Doc ET-01</span>
        <span className="whitespace-nowrap border-l border-hairline px-6 py-3 text-ink-muted">Rev. 2026.08</span>
        <span className="whitespace-nowrap border-l border-hairline px-6 py-3 text-ink-muted">Sheet 1 of 1</span>
      </div>
      {STEPS.map((s, i) => (
        <div
          key={s.num}
          className="grid grid-cols-2 gap-4 px-6 py-[22px] md:grid-cols-[64px_210px_1fr_140px] md:items-baseline md:gap-6"
          style={{ borderBottom: i === STEPS.length - 1 ? "0" : "1px solid var(--rule)" }}
        >
          <span className="num text-[13px] text-accent-deep">{s.num}</span>
          <span className="font-display text-[19px] font-semibold uppercase tracking-[.03em] text-ink">
            {s.title}
          </span>
          <span className="col-span-2 text-[14.5px] leading-[1.6] text-ink md:col-span-1">{s.body}</span>
          <span
            className="justify-self-start whitespace-nowrap font-display text-[10.5px] font-semibold uppercase tracking-[.08em]"
            style={
              s.planned
                ? { padding: "6px 9px", color: "var(--ink-muted)", border: "1px dashed var(--field)" }
                : { padding: "6px 9px", color: "var(--accent-deep)", background: "var(--accent-tint)", border: "1px solid var(--accent)" }
            }
          >
            {s.tag}
          </span>
        </div>
      ))}
    </div>
  );
}

export function LandingPage({ onTryDemo }) {
  const [demoState, setDemoState] = useState("idle"); // idle | loading | error

  const viewDemo = async () => {
    if (!auth) return;
    setDemoState("loading");
    try {
      await signInWithEmailAndPassword(auth, DEMO_EMAIL, DEMO_PASSWORD);
      window.location.href = "/";
    } catch {
      setDemoState("error");
    }
  };

  return (
    <div style={{ minHeight: "100vh", background: "var(--ground)" }}>
      <header className="sticky top-0 z-10 flex items-center gap-7 border-b border-hairline bg-surface px-5 sm:px-[72px]">
        <div className="flex items-center gap-2.5 py-[18px]">
          <LogoMark />
          <span className="font-display text-[18px] font-semibold tracking-[.03em] text-ink">
            EXPENSE TRACKER
          </span>
        </div>
        <nav className="ml-3 hidden gap-[22px] sm:flex">
          {NAV_LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="whitespace-nowrap font-display text-[13px] font-semibold uppercase tracking-[.07em] text-ink no-underline hover:text-accent-deep"
            >
              {link.label}
            </a>
          ))}
        </nav>
        <span className="ml-auto flex items-center gap-4">
          <a
            href={GITHUB_URL}
            target="_blank"
            rel="noreferrer"
            className="hidden whitespace-nowrap font-display text-[12.5px] font-semibold uppercase tracking-[.06em] text-ink-muted no-underline hover:text-accent-deep sm:inline"
          >
            View source
          </a>
          <button
            onClick={onTryDemo}
            className="blueprint relative whitespace-nowrap bg-accent-deep px-[18px] py-3 font-display text-[13px] font-semibold uppercase tracking-[.05em] text-ground hover:bg-accent-press"
          >
            <Corners />
            Connect your bank
          </button>
        </span>
      </header>

      <section className="mx-auto max-w-[1200px] px-5 pb-[72px] pt-24 sm:px-[72px]">
        <h1 className="m-0 font-display text-[clamp(48px,7vw,92px)] font-semibold uppercase leading-[1.04] tracking-[.01em] text-ink">
          <span className="block">See what you can afford</span>
          <span className="block text-accent-deep">before you spend it.</span>
        </h1>
        <p className="m-0 mt-8 max-w-[62ch] text-[17px] leading-[1.6] text-ink">
          Connect your bank through Plaid and Expense Tracker checks purchases against your real
          budget, tracks savings goals, and flags subscriptions quietly working against them. It's
          free to use, and the source is public — nothing about how it handles your data is hidden.
        </p>
        <div className="mt-8 flex flex-wrap items-center gap-5">
          <button
            onClick={onTryDemo}
            className="blueprint relative bg-accent-deep px-[26px] py-4 font-display text-[15px] font-semibold uppercase tracking-[.05em] text-ground hover:bg-accent-press"
          >
            <Corners />
            Connect your bank
          </button>
          <button
            type="button"
            onClick={viewDemo}
            disabled={demoState === "loading"}
            className="whitespace-nowrap border border-field bg-transparent px-[22px] py-[15px] font-display text-[14px] font-semibold uppercase tracking-[.05em] text-ink hover:bg-sunken disabled:opacity-50"
          >
            {demoState === "loading" ? "Loading…" : "View live demo"}
          </button>
          <a
            href={GITHUB_URL}
            target="_blank"
            rel="noreferrer"
            className="whitespace-nowrap font-display text-[13px] font-semibold uppercase tracking-[.05em] text-ink-muted no-underline hover:text-accent-deep"
          >
            View source &rarr;
          </a>
        </div>
        {demoState === "error" && (
          <p className="m-0 mt-3 text-[13px] text-crit">Couldn't load the demo right now — try again in a moment.</p>
        )}
      </section>

      <section className="mx-auto max-w-[1200px] px-5 pb-24 sm:px-[72px]">
        <div className="mb-3 flex flex-wrap items-baseline justify-between gap-4">
          <span className="font-display text-[13px] font-semibold uppercase tracking-[.08em] text-accent-deep">
            The dashboard
          </span>
          <span className="font-mono text-[12.5px] text-ink-faint">demo data &middot; August 2026</span>
        </div>
        <hr className="mb-6 h-px border-0 bg-hairline" />
        <DashboardPreview />
      </section>

      <section className="mx-auto max-w-[1200px] px-5 pb-24 sm:px-[72px]">
        <div className="mb-3 flex flex-wrap items-baseline justify-between gap-4">
          <span className="font-display text-[13px] font-semibold uppercase tracking-[.08em] text-accent-deep">
            The affordability check
          </span>
          <span className="font-mono text-[12.5px] text-ink-faint">example &middot; deterministic math</span>
        </div>
        <hr className="mb-6 h-px border-0 bg-hairline" />
        <AffordabilityExample />
      </section>

      <section id="how" className="mx-auto max-w-[1200px] scroll-mt-[76px] px-5 pb-24 sm:px-[72px]">
        <span className="mb-3 block font-display text-[13px] font-semibold uppercase tracking-[.08em] text-accent-deep">
          Sheet 01 &middot; How it works
        </span>
        <hr className="mb-7 h-px border-0 bg-hairline" />
        <HowItWorksSheet />
      </section>

      <section id="privacy" className="mx-auto max-w-[1200px] scroll-mt-[76px] px-5 pb-24 sm:px-[72px]">
        <span className="mb-3 block font-display text-[13px] font-semibold uppercase tracking-[.08em] text-accent-deep">
          02 &middot; What is stored, and where it goes
        </span>
        <hr className="mb-7 h-px border-0 bg-hairline" />
        <p className="m-0 mb-7 max-w-[64ch] text-[16px] leading-[1.6] text-ink">
          Signing in creates an Expense Tracker account, separate from your bank login. The only
          parties in the loop after that are you, your bank, and Plaid.
        </p>
        <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
          {PRIVACY.map((p) => (
            <div key={p.title} className="blueprint relative border border-hairline p-[22px] pb-6">
              <Corners />
              <div className="mb-3 font-mono text-[10px] font-medium uppercase tracking-[.12em] text-ink-faint">
                {p.label}
              </div>
              <div className="mb-2.5 font-display text-[21px] font-semibold uppercase tracking-[.03em] text-ink">
                {p.title}
              </div>
              <p className="m-0 text-[14px] leading-[1.6] text-ink">{p.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-[1200px] px-5 pb-24 sm:px-[72px]">
        <InterestForm />
      </section>

      <footer className="border-t border-hairline bg-sunken">
        <div className="mx-auto flex max-w-[1200px] flex-col gap-4 px-5 py-8 pb-10 sm:px-[72px]">
          <p className="m-0 max-w-[92ch] text-[13.5px] leading-[1.6] text-ink-muted">
            This is a personal project, not a bank or licensed financial service. It shows you
            your own transactions and the budgets you set; it does not give financial advice,
            hold money, or move it.
          </p>
          <details>
            <summary className="cursor-pointer list-none font-display text-[13px] font-semibold uppercase tracking-[.07em] text-accent-deep">
              What data is stored, and where it goes &#8964;
            </summary>
            <p className="m-0 mt-3 max-w-[96ch] text-[14px] leading-[1.65] text-ink">
              Your Plaid access token is encrypted at rest on the server and never sent back to
              the browser. Transactions and budgets are stored in that same database, scoped to
              your account. There's no analytics service, no tracking pixel, and no third-party
              script on this page or in the app. The storage code is in{" "}
              <span className="bg-[color-mix(in_srgb,var(--ink)_10%,transparent)] px-1.5 py-0.5 font-mono text-[13px]">
                backend/app/db.py
              </span>{" "}
              — read it before you trust it.
            </p>
          </details>
          <p className="m-0 font-mono text-[12.5px] text-ink-faint">
            MIT licensed &middot; React + Vite + FastAPI &middot; free to use
          </p>
          <div className="flex flex-wrap gap-[22px] pt-1.5">
            <a
              href={GITHUB_URL}
              target="_blank"
              rel="noreferrer"
              className="font-display text-[12.5px] font-semibold uppercase tracking-[.07em] text-ink no-underline hover:text-accent-deep"
            >
              GitHub
            </a>
            <a
              href={`${GITHUB_URL}/issues`}
              target="_blank"
              rel="noreferrer"
              className="font-display text-[12.5px] font-semibold uppercase tracking-[.07em] text-ink no-underline hover:text-accent-deep"
            >
              Issues
            </a>
            <span className="ml-auto font-mono text-[12.5px] text-ink-faint">&copy; 2026</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
