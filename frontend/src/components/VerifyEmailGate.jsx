import { useState } from "react";
import { sendEmailVerification } from "firebase/auth";
import { auth } from "../firebase";
import { Corners } from "./Corners";

export function VerifyEmailGate({ email }) {
  const [state, setState] = useState("idle"); // idle | sending | sent | error

  const resend = async () => {
    if (!auth?.currentUser) return;
    setState("sending");
    try {
      await sendEmailVerification(auth.currentUser);
      setState("sent");
    } catch {
      setState("error");
    }
  };

  return (
    <div className="blueprint relative border border-hairline bg-ground">
      <Corners />
      <div className="px-[30px] py-10">
        <div className="mb-3.5 font-mono text-[10px] font-medium uppercase tracking-[.14em] text-ink-faint">
          Step 1 of 2
        </div>
        <h1 className="mb-3 font-display text-[38px] font-semibold leading-[1.05] text-ink">
          Verify your email first
        </h1>
        <p className="mb-6 max-w-[46ch] text-[15px] leading-[1.6] text-ink">
          We sent a link to {email}. Confirm it's really you before connecting a bank account —
          click the link, then come back here.
        </p>

        <button
          type="button"
          onClick={resend}
          disabled={state === "sending"}
          className="blueprint relative inline-flex items-center bg-accent-deep px-6 py-3.5 font-display text-[15px] font-semibold uppercase tracking-[.05em] text-ground hover:bg-accent-press disabled:opacity-50"
        >
          <Corners />
          {state === "sending" ? "Sending…" : state === "sent" ? "Sent again — check your inbox" : "Resend email"}
        </button>
        {state === "error" && <p className="mt-3 text-[13px] text-crit">Couldn't resend — try again shortly.</p>}

        <p className="mt-4 text-[12.5px] text-ink-faint">
          Already clicked the link? Refresh this page or switch tabs and back — it picks up
          automatically.
        </p>
      </div>
    </div>
  );
}
