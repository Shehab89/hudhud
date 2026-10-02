"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import type { Locale } from "@/lib/i18n";
import { locate, MODULES, num2, t } from "@/lib/modules";

export default function ModulesMenu({ l, label, home }: { l: Locale; label: string; home: string }) {
  const [open, setOpen] = useState(false);
  const pathname = usePathname() ?? "";
  const ref = useRef<HTMLDivElement>(null);
  const cur = locate(pathname)?.mod.key;
  useEffect(() => {
    const away = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", away); document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", away); document.removeEventListener("keydown", esc); };
  }, []);
  return (
    <div ref={ref} className="relative">
      <button type="button" aria-expanded={open} aria-haspopup="true" onClick={() => setOpen((o) => !o)}
        className={`flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm font-medium ${open || cur ? "border-accent text-accent" : "border-line"}`}>
        <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden fill="currentColor"><rect width="6" height="6" rx="1" /><rect x="8" width="6" height="6" rx="1" /><rect y="8" width="6" height="6" rx="1" /><rect x="8" y="8" width="6" height="6" rx="1" /></svg>
        {label} <span aria-hidden>▾</span>
      </button>
      {open && (
        <div className="absolute start-0 mt-2 w-[min(92vw,44rem)] rounded-lg border border-line bg-surface shadow-xl p-2 grid sm:grid-cols-2 gap-1">
          <Link href={`/${l}`} onClick={() => setOpen(false)} className="sm:col-span-2 px-3 py-2 rounded-md hover:bg-surface-2 text-sm text-muted">← {home}</Link>
          {MODULES.map((m) => (
            <Link key={m.key} href={`/${l}${m.href}`} onClick={() => setOpen(false)} aria-current={cur === m.key ? "page" : undefined}
              className={`flex gap-3 rounded-md px-3 py-2.5 hover:bg-surface-2 ${cur === m.key ? "bg-surface-2" : ""}`}>
              <span className="num text-accent font-semibold text-sm pt-0.5">{num2(m.n, l)}</span>
              <span className="min-w-0">
                <span className="block font-medium text-sm">{t(m.title, l)}</span>
                <span className="block text-xs text-muted leading-snug line-clamp-2">{t(m.blurb, l)}</span>
              </span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
