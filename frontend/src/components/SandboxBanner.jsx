export function SandboxBanner({ isSandbox }) {
  if (!isSandbox) return null;

  return (
    <div
      role="status"
      className="flex items-center gap-2.5 border-b border-warn-br bg-warn-bg px-[30px] py-3 text-[13.5px] text-sandbox-text"
    >
      <span className="h-[7px] w-[7px] flex-none rounded-full bg-warn" />
      <strong className="font-semibold">Demo mode</strong>
      <span>Using simulated bank data from the Plaid Sandbox. No real accounts are connected.</span>
    </div>
  );
}
