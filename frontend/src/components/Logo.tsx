/** Hudhud mark: a hoopoe whose crest is a fan of signal bars. Body and eye follow the theme ink. */
export default function Logo({ className = "size-8" }: { className?: string }) {
  return (
    <svg viewBox="8 6 104 106" className={className} aria-hidden focusable="false">
      <g strokeLinecap="round" strokeWidth="8">
        <line x1="52" y1="56" x2="30" y2="30" stroke="#C8553D" />
        <line x1="54" y1="54" x2="44" y2="18" stroke="#D9773B" />
        <line x1="57" y1="53" x2="60" y2="12" stroke="#E0A458" />
        <line x1="60" y1="54" x2="76" y2="20" stroke="#D9773B" />
      </g>
      <g fill="var(--ink)" stroke="var(--ink)">
        <circle cx="60" cy="66" r="18" stroke="none" />
        <path d="M74 64L104 72L74 74z" strokeLinejoin="round" strokeWidth="2" />
        <path d="M44 74C40 92 52 106 74 106L58 82z" stroke="none" />
      </g>
      <circle cx="64" cy="63" r="3.5" fill="var(--bg)" />
      <g fill="#E0A458">
        <rect x="20" y="100" width="6" height="8" rx="1" />
        <rect x="29" y="94" width="6" height="14" rx="1" />
        <rect x="38" y="88" width="6" height="20" rx="1" />
      </g>
    </svg>
  );
}
