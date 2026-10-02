/** Placeholder mark until a name and logo are chosen: an arched window (qamariya) over a baseline. */
export default function Logo({ className = "size-8" }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden focusable="false">
      <rect x="1" y="1" width="30" height="30" rx="7" fill="var(--accent)" />
      <path d="M9 24V15a7 7 0 0 1 14 0v9" fill="none" stroke="var(--accent-ink)" strokeWidth="2.2" />
      <path d="M16 8.5v15.5M9.5 16.5h13" stroke="var(--accent-ink)" strokeWidth="1.4" opacity="0.75" />
      <circle cx="16" cy="13" r="2" fill="var(--accent-ink)" />
      <path d="M6 24.5h20" stroke="var(--accent-ink)" strokeWidth="2.2" strokeLinecap="round" />
    </svg>
  );
}
