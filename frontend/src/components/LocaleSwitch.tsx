"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

export default function LocaleSwitch({ locale, label }: { locale: string; label: string }) {
  const pathname = usePathname() || "/";
  const sp = useSearchParams();
  const other = locale === "ar" ? "en" : "ar";
  const rest = pathname.replace(/^\/(en|ar)(?=\/|$)/, "");
  const qs = sp?.toString();
  return (
    <Link href={`/${other}${rest}${qs ? `?${qs}` : ""}`} hrefLang={other} lang={other}
      className="rounded-md border border-line px-2.5 py-1.5 text-sm hover:bg-surface-2">
      {label}
    </Link>
  );
}
