import Link from "next/link";
import { Suspense } from "react";
import type { Dict, Locale } from "@/lib/i18n";
import LocaleSwitch from "./LocaleSwitch";
import Logo from "./Logo";
import ModulesMenu from "./ModulesMenu";
import ThemeToggle from "./ThemeToggle";

export default function Header({ l, d }: { l: Locale; d: Dict }) {
  const p = (s: string) => `/${l}${s}`;
  const util = "px-2 py-1 rounded hover:text-ink hover:bg-surface-2";
  return (
    <header className="sticky z-30 bg-surface border-b border-line" style={{ top: "env(safe-area-inset-top, 0px)" }}>
      <div className="bg-surface-2 border-b border-line text-xs text-muted">
        <div className="mx-auto max-w-7xl px-4 py-1 flex items-center justify-between gap-3">
          <span className="hidden sm:block truncate">{d.site.tagline}</span>
          <nav aria-label="Secondary" className="flex items-center gap-1 ms-auto">
            <Link href={p("/methodology")} className={util}>{d.nav.methodology}</Link>
            <Link href={p("/about")} className={util}>{d.nav.about}</Link>
            <Link href={p("/admin")} className={util}>{d.nav.admin}</Link>
            <span className="mx-1 h-4 w-px bg-line" aria-hidden />
            <Suspense fallback={null}><LocaleSwitch locale={l} label={d.nav.language} /></Suspense>
            <ThemeToggle label={d.nav.theme} />
          </nav>
        </div>
      </div>
      <div className="mx-auto max-w-7xl px-4 py-2.5 flex items-center gap-3">
        <Link href={p("")} className="flex items-center gap-2.5 me-2" aria-label={d.site.name}>
          <Logo />
          <span className="font-semibold text-lg leading-none">{d.site.name}</span>
        </Link>
        <ModulesMenu l={l} label={l === "ar" ? "الوحدات" : "Modules"} home={l === "ar" ? "الصفحة الرئيسية" : "Home"} />
        <form action={p("/news")} method="get" role="search" className="ms-auto flex-1 max-w-sm">
          <input name="q" type="search" aria-label={d.common.search} placeholder={d.common.search + "…"}
            className="w-full rounded-md border border-line bg-bg px-3 py-1.5 text-sm" />
        </form>
      </div>
    </header>
  );
}
