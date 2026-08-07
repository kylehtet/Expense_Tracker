export function SandboxBanner({ isSandbox }) {
  if (!isSandbox) return null;

  return (
    <div
      role="status"
      className="w-full bg-[var(--status-warning)] px-4 py-2 text-center text-sm font-medium text-[#1a1a19]"
    >
      Demo mode — using simulated bank data.
    </div>
  );
}
