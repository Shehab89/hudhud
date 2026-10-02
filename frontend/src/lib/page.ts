import { notFound } from "next/navigation";
import type { SearchParams } from "./api";
import { getDict, hasLocale, type Dict, type Locale } from "./i18n";

export type PageProps<P = object> = { params: Promise<{ locale: string } & P>; searchParams: Promise<SearchParams> };

/** Resolve locale, dictionary, route params and search params for a page. */
export async function setup<P extends object = object>(props: PageProps<P>): Promise<{ l: Locale; d: Dict; p: P & { locale: string }; sp: SearchParams }> {
  const p = await props.params;
  if (!hasLocale(p.locale)) notFound();
  return { l: p.locale, d: getDict(p.locale), p, sp: await props.searchParams };
}

export const one = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v) ?? "";
