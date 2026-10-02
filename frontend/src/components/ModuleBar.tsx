"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { Locale } from "@/lib/i18n";
import { locate, num2, t } from "@/lib/modules";

/** Breadcrumb and in-module tabs, shown under the header on every module page. */
export default function ModuleBar({ l, home }: { l: Locale; home: string }) {
  const hit = locate(usePathname() ?? "");
  if (!hit) return null;
  const { mod, tab } = hit;
  return (
    <div className="border-b border-line bg-bg">
      <div className="mx-auto max-w-7xl px-4 pt-3 flex flex-col gap-2">
        <nav aria-label="Breadcrumb" className="text-xs text-muted flex items-center gap-1.5">
          <Link href={`/${l}`} className="hover:underline">{home}</Link><span aria-hidden>/</span>
          <span className="text-ink">{t(mod.title, l)}</span>
        </nav>
        <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-1">
          <p className="flex items-baseline gap-2.5 text-lg font-semibold">
            <span className="num text-accent">{num2(mod.n, l)}</span>{t(mod.title, l)}
          </p>
          <div role="tablist" className="flex gap-1 overflow-x-auto -mb-px">
            {mod.tabs.map((x) => (
              <Link key={x.href} role="tab" aria-selected={x === tab} href={`/${l}${x.href}`}
                className={`whitespace-nowrap px-3 py-2 text-sm border-b-2 ${x === tab ? "border-accent text-ink font-medium" : "border-transparent text-muted hover:text-ink"}`}>
                {t(x.label, l)}
              </Link>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
