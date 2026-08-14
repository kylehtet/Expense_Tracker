import { useState } from "react";
import { api } from "../api";
import { Corners } from "./Corners";

export function InterestForm() {
  const [email, setEmail] = useState("");
  const [state, setState] = useState("idle"); // idle | loading | done | error
  const [message, setMessage] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setState("loading");
    setMessage(null);
    try {
      await api.submitInterest(email);
      setState("done");
    } catch (err) {
      setState("error");
      setMessage(err.status === 429 ? "Try again in a moment." : "Couldn't submit that. Try again.");
    }
  };

  if (state === "done") {
    return (
      <div className="blueprint relative border border-hairline bg-ground px-[34px] py-10 text-center">
        <Corners />
        <div className="mb-2 font-display text-[22px] font-semibold uppercase tracking-[.03em] text-ink">
          You're on the list
        </div>
        <p className="m-0 text-[14px] text-ink-muted">
          No spam, no mailing list - just a note when this is ready for more than just me.
        </p>
      </div>
    );
  }

  return (
    <div className="blueprint relative border border-hairline bg-ground px-[34px] py-10">
      <Corners />
      <div className="mb-1 font-display text-[22px] font-semibold uppercase tracking-[.03em] text-ink">
        Want in when it's ready?
      </div>
      <p className="m-0 mb-6 max-w-[52ch] text-[14px] leading-[1.6] text-ink-muted">
        This is a working personal project, currently just me testing it on my own account before
        opening it up further. Leave your email and I'll let you know when it's ready for more people.
      </p>
      <form onSubmit={handleSubmit} className="flex flex-wrap items-start gap-3">
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@example.com"
          className="h-[46px] min-w-[240px] flex-1 border border-field bg-surface px-3.5 text-[14px] text-ink outline-none focus:border-accent"
        />
        <button
          type="submit"
          disabled={state === "loading"}
          className="blueprint relative inline-flex h-[46px] items-center justify-center bg-accent-deep px-6 font-display text-[14px] font-semibold uppercase tracking-[.05em] text-ground hover:bg-accent-press disabled:opacity-50"
        >
          <Corners />
          {state === "loading" ? "Submitting…" : "Notify me"}
        </button>
      </form>
      {message && <p className="mt-3 text-[13px] text-crit">{message}</p>}
    </div>
  );
}
