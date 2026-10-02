import en from "@/dictionaries/en.json";
import ar from "@/dictionaries/ar.json";

export const locales = ["en", "ar"] as const;
export type Locale = (typeof locales)[number];
export type Dict = typeof en;

const dictionaries: Record<Locale, Dict> = { en, ar: ar as Dict };

export const hasLocale = (l: string): l is Locale => (locales as readonly string[]).includes(l);
export const getDict = (l: Locale): Dict => dictionaries[l];
export const dirOf = (l: Locale) => (l === "ar" ? "rtl" : "ltr");

export function fmtNumber(n: number | null | undefined, l: Locale, opts?: Intl.NumberFormatOptions) {
  if (n === null || n === undefined) return "–";
  return new Intl.NumberFormat(l === "ar" ? "ar-EG" : "en-GB", opts).format(n);
}

export function fmtDate(d: string | Date | null | undefined, l: Locale, opts?: Intl.DateTimeFormatOptions) {
  if (!d) return "–";
  const date = typeof d === "string" ? new Date(d) : d;
  return new Intl.DateTimeFormat(l === "ar" ? "ar-EG-u-nu-latn" : "en-GB", opts ?? { day: "numeric", month: "short", year: "numeric" }).format(date);
}

/** Pick the Arabic label when the UI is Arabic and one exists. */
export function pick(l: Locale, en_: string | null | undefined, ar_: string | null | undefined) {
  return (l === "ar" && ar_) || en_ || ar_ || "";
}
