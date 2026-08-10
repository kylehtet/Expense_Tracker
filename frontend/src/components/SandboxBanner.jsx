// Persistent, always-visible indicator of which Plaid environment is live -
// demo (Sandbox) and real (Production) data should never look identical.
export function SandboxBanner({ isSandbox }) {
  if (isSandbox == null) return null; // /config hasn't loaded yet

  if (isSandbox) {
    return (
      <div
        role="status"
        className="flex items-center gap-2.5 border-b border-warn-br bg-warn-bg px-[30px] py-3 text-[13.5px] text-sandbox-text"
      >
        <span className="h-[7px] w-[7px] flex-none rounded-full bg-warn" />
        <strong className="font-semibold">Demo data</strong>
        <span>Using simulated bank data from the Plaid Sandbox. No real accounts are connected.</span>
      </div>
    );
  }

  return (
    <div
      role="status"
      className="flex items-center gap-2.5 border-b border-crit-br bg-crit-bg px-[30px] py-3 text-[13.5px] text-crit"
    >
      <span className="h-[7px] w-[7px] flex-none rounded-full bg-crit" />
      <strong className="font-semibold">Live data</strong>
      <span>Connected through Plaid Production. This is a real bank account, not a demo.</span>
    </div>
  );
}
