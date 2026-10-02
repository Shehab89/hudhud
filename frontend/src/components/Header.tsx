import Link from "next/link";
import { Suspense } from "react";
import type { Dict, Locale } from "@/lib/i18n";
import LocaleSwitch from "./LocaleSwitch";
import Logo from "./Logo";
import Nav from "./Nav";
import ThemeToggle from "./ThemeToggle";

export default function Header({ l, d }: { l: Locale; d: Dict }) {
  const p = (s: string) => `/${l}${s}`;
  const items = [
    { href: p(""), label: d.nav.dashboard, primary: true },
    { href: p("/news"), label: d.nav.news, primary: true },
    { href: p("/topics"), label: d.nav.topics, primary: true },
    { href: p("/sources"), label: d.nav.sources, primary: true },
    { href: p("/actors"), label: d.nav.actors, primary: true },
    { href: p("/events"), label: d.nav.events, primary: true },
    { href: p("/research"), label: d.nav.research, primary: true },
    { href: p("/geography"), label: d.nav.geography, primary: false },
    { href: p("/media-landscape"), label: d.nav.landscape, primary: false },
    { href: p("/methodology"), label: d.nav.methodology, primary: false },
    { href: p("/quality"), label: d.nav.quality, primary: false },
    { href: p("/about"), label: d.nav.about, primary: false },
    { href: p("/admin"), label: d.nav.admin, primary: false },
  ];
  return (
    <header className="border-b border-line bg-surface/80 backdrop-blur sticky z-20" style={{ top: "env(safe-area-inset-top, 0px)" }}>
      <div className="mx-auto max-w-7xl px-4 py-3 flex flex-wrap items-center gap-x-6 gap-y-2">
        <Link href={p("")} className="flex items-center gap-2.5 me-2">
          <Logo />
          <span className="flex flex-col leading-tight">
            <span className="font-semibold">{d.site.name}</span>
            <span className="text-[0.7rem] text-muted hidden sm:block">{d.site.tagline}</span>
          </span>
        </Link>
        <div className="flex-1 min-w-0"><Nav items={items} moreLabel={d.nav.more} /></div>
        <div className="flex items-center gap-2">
          <Suspense fallback={null}><LocaleSwitch locale={l} label={d.nav.language} /></Suspense>
          <ThemeToggle label={d.nav.theme} />
        </div>
      </div>
    </header>
  );
}
