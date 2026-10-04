import Link from "next/link";
import type { ArticleSummary } from "@/lib/api";
import type { Dict, Locale } from "@/lib/i18n";
import { fmtDate } from "@/lib/i18n";
import { BaseBadge, ContentTypeBadge, DemoBadge, SentimentBadge } from "./ui";

export default function ArticleItem({ a, l, d, extra }: { a: ArticleSummary; l: Locale; d: Dict; extra?: React.ReactNode }) {
  const rtl = a.language === "ar" || a.language === "fa" || a.language === "he" || a.language === "ur";
  return (
    <li className="py-3 border-b border-line last:border-0 flex flex-col gap-1.5 min-w-0">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
        <span className="font-medium text-ink">{a.publisher_name || a.source.name}</span>
        <ContentTypeBadge type={a.source.content_type} l={l} />
        {a.source.region === "yemen" || !a.source.region ? <BaseBadge base={a.source.operating_base} d={d} /> : null}
        <time dateTime={a.published_at ?? undefined} className="num">{fmtDate(a.published_at, l, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}</time>
        <span className="uppercase">{a.language}</span>
        {a.is_syndicated && <span>· {d.common.syndicated}</span>}
        {a.is_demo && <DemoBadge d={d} />}
      </div>
      <Link href={`/${l}/news/${a.id}`} className="font-medium leading-snug hover:underline underline-offset-2" lang={a.language ?? undefined} dir={rtl ? "rtl" : "ltr"}>
        {a.title}
      </Link>
      {a.excerpt && <p className="text-sm text-muted line-clamp-2" lang={a.language ?? undefined} dir={rtl ? "rtl" : "ltr"}>{a.excerpt}</p>}
      <div className="flex flex-wrap items-center gap-2">
        <SentimentBadge value={a.sentiment} d={d} />
        {a.primary_category && <span className="text-xs text-muted font-mono">{a.primary_category}</span>}
        {extra}
      </div>
    </li>
  );
}
