import { useState } from "react";
import { signInWithEmailAndPassword } from "firebase/auth";
import { auth } from "../firebase";
import { Corners } from "./Corners";

const ERROR_MESSAGES = {
  "auth/invalid-credential": "Incorrect email or password.",
  "auth/user-not-found": "Incorrect email or password.",
  "auth/wrong-password": "Incorrect email or password.",
  "auth/invalid-email": "That doesn't look like a valid email address.",
  "auth/too-many-requests": "Too many attempts. Try again in a few minutes.",
  "auth/user-disabled": "This account has been disabled.",
};

export function CustomLogin() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [state, setState] = useState("idle"); // idle | loading | error
  const [message, setMessage] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!auth) {
      setState("error");
      setMessage("Firebase isn't configured yet - check the frontend .env file.");
      return;
    }
    setState("loading");
    setMessage(null);
    try {
      await signInWithEmailAndPassword(auth, email, password);
      window.location.href = "/";
    } catch (err) {
      setState("error");
      setMessage(ERROR_MESSAGES[err.code] || "Something went wrong. Try again.");
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

          <h1 className="mb-1.5 font-display text-[26px] font-semibold leading-[1.1] text-ink">Log in</h1>
          <p className="mb-6 text-[14px] leading-[1.55] text-ink-muted">
            Enter your email and password to continue.
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
            <div>
              <label className="mb-1.5 block font-mono text-[10px] font-medium uppercase tracking-[.12em] text-ink-faint">
                Password
              </label>
              <input
                type="password"
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="h-[46px] w-full border border-field bg-surface px-3.5 text-[14px] text-ink outline-none focus:border-accent"
              />
            </div>

            {message && <p className="text-[13px] leading-[1.5] text-crit">{message}</p>}

            <button
              type="submit"
              disabled={state === "loading"}
              className="blueprint relative mt-1 inline-flex items-center justify-center bg-accent-deep px-6 py-3.5 font-display text-[15px] font-semibold uppercase tracking-[.05em] text-ground hover:bg-accent-press disabled:opacity-50"
            >
              <Corners />
              {state === "loading" ? "Logging in…" : "Log in"}
            </button>
          </form>

          <div className="mt-6 border-t border-rule pt-5 text-[13px]">
            <a
              href="/signup"
              className="font-display font-semibold uppercase tracking-[.04em] text-accent-deep hover:text-accent-press"
            >
              Don&apos;t have an account? Sign up &rarr;
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
