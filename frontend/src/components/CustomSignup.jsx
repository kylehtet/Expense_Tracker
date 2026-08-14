import { useState } from "react";
import { createUserWithEmailAndPassword, sendEmailVerification } from "firebase/auth";
import { auth } from "../firebase";
import { Corners } from "./Corners";
import { PasswordField } from "./PasswordField";

const ERROR_MESSAGES = {
  "auth/email-already-in-use": "An account with that email already exists.",
  "auth/invalid-email": "That doesn't look like a valid email address.",
  "auth/weak-password": "Password must be at least 6 characters.",
  "auth/too-many-requests": "Too many attempts. Try again in a few minutes.",
};

export function CustomSignup() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [state, setState] = useState("idle"); // idle | loading | error
  const [message, setMessage] = useState(null);
  const [agreed, setAgreed] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!agreed) {
      setState("error");
      setMessage("Please agree to the Privacy Policy to continue.");
      return;
    }
    if (password !== confirmPassword) {
      setState("error");
      setMessage("Passwords don't match.");
      return;
    }
    if (!auth) {
      setState("error");
      setMessage("Firebase isn't configured yet - check the frontend .env file.");
      return;
    }
    setState("loading");
    setMessage(null);
    try {
      const credential = await createUserWithEmailAndPassword(auth, email, password);
      // Must be awaited before navigating - window.location.href below tears
      // down the page immediately, which aborts any still-in-flight request,
      // including this one if it isn't awaited first. Best-effort beyond
      // that: a failure here shouldn't block account creation, the in-app
      // gate's "Resend" button covers this case too.
      await sendEmailVerification(credential.user).catch(() => {});
      window.location.href = "/";
    } catch (err) {
      setState("error");
      setMessage(ERROR_MESSAGES[err.code] || "Couldn't create your account. Try again.");
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-ground px-6">
      <div className="blueprint relative w-full max-w-[420px] border border-hairline bg-ground">
        <Corners />
        <div className="px-[30px] py-10">
          <div className="mb-6 flex items-center gap-2.5">
            <span className="relative block h-[17px] w-[17px] border-[1.5px] border-accent-deep">
              <span className="absolute bottom-0.5 left-0.5 h-[5px] w-[3px] bg-accent-deep" />
              <span className="absolute bottom-0.5 left-[7px] h-[10px] w-[3px] bg-accent-deep" />
              <span className="absolute bottom-0.5 left-3 h-[7px] w-[3px] bg-accent-deep" />
            </span>
            <span className="font-display text-[17px] font-semibold tracking-[.02em] text-ink">
              EXPENSE TRACKER
            </span>
          </div>

          <h1 className="mb-1.5 font-display text-[26px] font-semibold leading-[1.1] text-ink">
            Create an account
          </h1>
          <p className="mb-6 text-[14px] leading-[1.55] text-ink-muted">
            Sign up to start tracking your spending.
          </p>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div>
              <label className="mb-1.5 block font-mono text-[10px] font-medium uppercase tracking-[.12em] text-ink-faint">
                Email
              </label>
              <input
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="h-[46px] w-full border border-field bg-surface px-3.5 text-[14px] text-ink outline-none focus:border-accent"
              />
            </div>
            <PasswordField
              label="Password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              hint={
                <p
                  className="mt-1.5 text-[12px]"
                  style={{ color: password.length >= 6 ? "var(--good)" : "var(--ink-faint)" }}
                >
                  {password.length >= 6 ? "✓" : "•"} At least 6 characters
                </p>
              }
            />
            <PasswordField
              label="Confirm password"
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
            />

            <label className="flex items-start gap-2.5 text-[13px] leading-[1.5] text-ink-muted">
              <input
                type="checkbox"
                checked={agreed}
                onChange={(e) => setAgreed(e.target.checked)}
                className="mt-[3px] h-[15px] w-[15px] flex-none accent-accent-deep"
              />
              <span>
                I agree to the{" "}
                <a
                  href="/privacy"
                  target="_blank"
                  rel="noreferrer"
                  className="font-semibold text-accent-deep hover:text-accent-press"
                >
                  Privacy Policy
                </a>
                .
              </span>
            </label>

            {message && <p className="text-[13px] leading-[1.5] text-crit">{message}</p>}

            <button
              type="submit"
              disabled={state === "loading"}
              className="blueprint relative mt-1 inline-flex items-center justify-center bg-accent-deep px-6 py-3.5 font-display text-[15px] font-semibold uppercase tracking-[.05em] text-ground hover:bg-accent-press disabled:opacity-50"
            >
              <Corners />
              {state === "loading" ? "Creating account…" : "Sign up"}
            </button>
          </form>

          <div className="mt-6 border-t border-rule pt-5 text-[13px]">
            <a
              href="/login"
              className="font-display font-semibold uppercase tracking-[.04em] text-accent-deep hover:text-accent-press"
            >
              Already have an account? Log in &rarr;
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
