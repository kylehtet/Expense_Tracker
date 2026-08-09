export function Logo({ onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex items-center gap-2.5 border-0 bg-transparent py-[17px] pl-0"
    >
      <span className="relative block h-[17px] w-[17px] border-[1.5px] border-accent-deep">
        <span className="absolute bottom-0.5 left-0.5 h-[5px] w-[3px] bg-accent-deep" />
        <span className="absolute bottom-0.5 left-[7px] h-[10px] w-[3px] bg-accent-deep" />
        <span className="absolute bottom-0.5 left-3 h-[7px] w-[3px] bg-accent-deep" />
      </span>
      <span className="font-display text-[17px] font-semibold tracking-[.02em] text-ink">
        EXPENSE TRACKER
      </span>
    </button>
  );
}
