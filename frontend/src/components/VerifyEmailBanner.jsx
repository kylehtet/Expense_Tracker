import { useState } from "react";
import { sendEmailVerification } from "firebase/auth";
import { auth } from "../firebase";

export function VerifyEmailBanner({ email }) {
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
    <div
      role="status"
      className="flex flex-wrap items-center gap-x-3 gap-y-1.5 border-b border-warn-br bg-warn-bg px-[30px] py-3 text-[13.5px] text-sandbox-text"
    >
      <span className="h-[7px] w-[7px] flex-none rounded-full bg-warn" />
      <strong className="font-semibold">Verify your email</strong>
      <span>
        We sent a link to {email}. {state === "sent" ? "Sent again — check your inbox." : "Check your inbox to confirm it's really you."}
      </span>
      <button
        type="button"
        onClick={resend}
        disabled={state === "sending"}
        className="font-display text-[12px] font-semibold uppercase tracking-[.05em] text-sandbox-text underline decoration-dotted hover:opacity-70 disabled:opacity-50"
      >
        {state === "sending" ? "Sending…" : "Resend email"}
      </button>
      {state === "error" && <span className="text-crit">Couldn't resend — try again shortly.</span>}
    </div>
  );
}
