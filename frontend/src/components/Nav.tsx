"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

export default function Nav({ items, moreLabel }: { items: { href: string; label: string; primary: boolean }[]; moreLabel: string }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const active = (href: string) => (href.split("/").length <= 2 ? pathname === href : pathname?.startsWith(href));
  const cls = (href: string) =>
    `whitespace-nowrap px-2.5 py-1.5 rounded-md text-sm ${active(href) ? "bg-surface-2 text-ink font-medium" : "text-muted hover:text-ink"}`;
  return (
    <nav aria-label="Main" className="flex flex-wrap items-center gap-1">
      {items.filter((i) => i.primary).map((i) => (
        <Link key={i.href} href={i.href} className={`hidden md:inline-block ${cls(i.href)}`} aria-current={active(i.href) ? "page" : undefined}>{i.label}</Link>
      ))}
      <div className="relative">
        <button type="button" className="px-2.5 py-1.5 rounded-md text-sm text-muted hover:text-ink" aria-expanded={open}
          onClick={() => setOpen((o) => !o)}>{moreLabel} ▾</button>
        {open && (
          <div className="absolute z-30 mt-1 min-w-48 rounded-md border border-line bg-surface p-1 shadow-lg end-0"
            onClick={() => setOpen(false)}>
            {items.map((i) => (
              <Link key={i.href} href={i.href} className={`${i.primary ? "block md:hidden" : "block"} ${cls(i.href)}`}>{i.label}</Link>
            ))}
          </div>
        )}
      </div>
    </nav>
  );
}
