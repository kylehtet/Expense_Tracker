import { useState } from "react";

export function PasswordField({ label, value, onChange, autoComplete, hint }) {
  const [visible, setVisible] = useState(false);

  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between gap-2">
        <label className="block font-mono text-[10px] font-medium uppercase tracking-[.12em] text-ink-faint">
          {label}
        </label>
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          tabIndex={-1}
          className="font-mono text-[10px] font-medium uppercase tracking-[.1em] text-accent-deep hover:text-accent-press"
        >
          {visible ? "Hide" : "Show"}
        </button>
      </div>
      <input
        type={visible ? "text" : "password"}
        required
        autoComplete={autoComplete}
        value={value}
        onChange={onChange}
        className="h-[46px] w-full border border-field bg-surface px-3.5 text-[14px] text-ink outline-none focus:border-accent"
      />
      {hint}
    </div>
  );
}
