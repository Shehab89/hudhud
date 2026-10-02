import Link from "next/link";
import type { Dict, Locale } from "@/lib/i18n";
import { PUBLIC_API_URL } from "@/lib/api";

export default function Footer({ l, d }: { l: Locale; d: Dict }) {
  return (
    <footer className="mt-16 border-t border-line bg-surface">
      <div className="mx-auto max-w-7xl px-4 py-8 grid gap-6 md:grid-cols-[2fr_1fr] text-sm">
        <div className="flex flex-col gap-3">
          <p className="text-muted leading-relaxed max-w-3xl">{d.site.disclaimer}</p>
          <p className="text-muted text-xs">{d.site.license}</p>
        </div>
        <ul className="flex flex-col gap-1.5 md:items-end">
          <li><Link className="hover:underline" href={`/${l}/methodology`}>{d.footer.methodology}</Link></li>
          <li><Link className="hover:underline" href={`/${l}/about`}>{d.footer.about}</Link></li>
          <li><Link className="hover:underline" href={`/${l}/quality`}>{d.nav.quality}</Link></li>
          <li><a className="hover:underline" href={`${PUBLIC_API_URL}/docs`}>{d.footer.api}</a></li>
        </ul>
      </div>
    </footer>
  );
}
