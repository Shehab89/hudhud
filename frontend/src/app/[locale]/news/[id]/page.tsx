import Link from "next/link";
import { notFound } from "next/navigation";
import DemoBanner from "@/components/DemoBanner";
import { BaseBadge, DemoBadge, Panel, Prov, SENTIMENT_COLORS, Section } from "@/components/ui";
import { tryApi, type ArticleDetail } from "@/lib/api";
import { fmtDate, fmtNumber, pick } from "@/lib/i18n";
import { setup, type PageProps } from "@/lib/page";

function Scores({ scores, colors }: { scores: Record<string, number>; colors?: Record<string, string> }) {
  const entries = Object.entries(scores).filter(([, v]) => typeof v === "number").sort((a, b) => b[1] - a[1]).slice(0, 6);
  return (
    <ul className="flex flex-col gap-1.5 text-sm">
      {entries.map(([k, v]) => (
        <li key={k} className="grid grid-cols-[7rem_1fr_3rem] items-center gap-2">
          <span className="truncate">{k}</span>
          <span className="h-1.5 rounded bg-surface-2"><span className="block h-1.5 rounded" style={{ width: `${Math.round(v * 100)}%`, background: colors?.[k] ?? "var(--accent-2)" }} /></span>
          <span className="num text-xs text-muted text-end">{v.toFixed(2)}</span>
        </li>
      ))}
    </ul>
  );
}

export default async function ArticlePage(props: PageProps<{ id: string }>) {
  const { l, d, p } = await setup(props);
  const a = await tryApi<ArticleDetail>(`/articles/${encodeURIComponent(p.id)}`);
  if (!a) notFound();
  const rtl = ["ar", "fa", "he", "ur"].includes(a.language.code ?? "");
  const sent = (d.sentiment as Record<string, string>);
  return (
    <article className="flex flex-col gap-8">
      <DemoBanner d={d} show={a.is_demo} />
      <header className="flex flex-col gap-3 border-b border-line pb-6">
        <div className="flex flex-wrap items-center gap-3 text-sm text-muted">
          <Link href={`/${l}/sources/${a.source.slug}`} className="font-medium text-ink hover:underline">{a.publisher_name || a.source.name}</Link>
          <BaseBadge base={a.source.operating_base} d={d} />
          <time className="num" dateTime={a.published_at ?? undefined}>{fmtDate(a.published_at, l, { dateStyle: "long", timeStyle: "short" })}</time>
          <span className="uppercase">{a.language.code}</span>
          {a.is_syndicated && <span>{d.common.syndicated}</span>}
          {a.is_demo && <DemoBadge d={d} />}
        </div>
        <h1 className="text-2xl md:text-3xl font-semibold leading-tight" lang={a.language.code ?? undefined} dir={rtl ? "rtl" : "ltr"}>{a.title}</h1>
        {a.excerpt && <p className={`text-lg text-muted max-w-3xl leading-relaxed ${rtl ? "self-end" : ""}`} lang={a.language.code ?? undefined} dir={rtl ? "rtl" : "ltr"}>{a.excerpt}</p>}
        <p className="text-xs text-muted">{d.article.excerptNote} {!a.is_demo && <a className="text-accent-2 underline" href={a.url} rel="noopener noreferrer" target="_blank">{d.common.readOriginal} ↗</a>}</p>
      </header>

      <Section title={d.article.analysis} note={d.article.separation}>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <Panel>
            <h3 className="label-caps text-muted mb-2">A · {d.article.a}</h3>
            {a.source.orientation ? (
              <p className="text-sm">{a.source.orientation.simplified.replaceAll("_", " ")} <span className="text-muted">({d.common.confidence} {a.source.orientation.confidence.toFixed(2)}, {a.source.orientation.method})</span></p>
            ) : <p className="text-sm text-muted">{d.common.unknown}</p>}
            <Link className="text-xs text-accent-2" href={`/${l}/sources/${a.source.slug}`}>{d.sources.history} →</Link>
          </Panel>
          <Panel>
            <h3 className="label-caps text-muted mb-2">B · {d.article.b}</h3>
            {a.sentiment.map((s, i) => (
              <div key={i} className="flex flex-col gap-2">
                <p className="font-medium" style={{ color: SENTIMENT_COLORS[s.polarity] }}>{sent[s.polarity] ?? s.polarity}</p>
                <Scores scores={s.scores} colors={SENTIMENT_COLORS} />
                <Prov p={s} d={d} />
              </div>
            ))}
            {a.emotions.map((e, i) => (
              <div key={i} className="mt-3 flex flex-col gap-1">
                <p className="text-sm"><span className="text-muted">{e.kind === "tone" ? d.common.tone : d.common.emotions}:</span> {e.dominant ?? d.common.none}</p>
                <Prov p={e} d={d} />
              </div>
            ))}
          </Panel>
          <Panel>
            <h3 className="label-caps text-muted mb-2">C · {d.article.c}</h3>
            {a.frames.length ? (
              <ul className="flex flex-col gap-3">
                {a.frames.map((f) => (
                  <li key={f.slug} className="flex flex-col gap-1">
                    <span className="font-medium text-sm">{pick(l, f.name_en, f.name_ar)} <span className="num text-muted">{f.score.toFixed(2)}</span></span>
                    {f.evidence_sentence && <blockquote className="border-s-2 border-accent ps-2 text-sm text-muted" dir="auto">“{f.evidence_sentence}”</blockquote>}
                    <Prov p={f} d={d} />
                  </li>
                ))}
              </ul>
            ) : <p className="text-sm text-muted">{d.common.none}</p>}
          </Panel>
          <Panel>
            <h3 className="label-caps text-muted mb-2">D · {d.article.d}</h3>
            <ul className="flex flex-col gap-2">
              {a.categories.map((c) => (
                <li key={c.slug} className="flex flex-col gap-0.5">
                  <span className="text-sm"><Link className="hover:underline" href={`/${l}/topics/category/${c.slug}`}>{pick(l, c.name_en, c.name_ar)}</Link> <span className="text-muted text-xs">{c.rank} · {c.score.toFixed(2)} · {d.article.route}: {c.route}</span></span>
                  <Prov p={c} d={d} />
                </li>
              ))}
              {a.topics.map((t) => (
                <li key={t.id} className="text-sm"><Link className="hover:underline" href={`/${l}/topics/${t.id}`}>{t.label}</Link> <span className="text-xs text-muted">{t.scope}</span></li>
              ))}
            </ul>
          </Panel>
          <Panel className="md:col-span-2">
            <h3 className="label-caps text-muted mb-2">E · {d.article.e}</h3>
            {a.targeted_sentiment.length ? (
              <ul className="flex flex-col gap-3">
                {a.targeted_sentiment.map((t, i) => (
                  <li key={i} className="flex flex-col gap-1">
                    <span className="text-sm"><Link className="font-medium hover:underline" href={`/${l}/actors/${t.entity}`}>{t.entity_name}</Link> · <span style={{ color: SENTIMENT_COLORS[t.sentiment] }}>{sent[t.sentiment] ?? t.sentiment}</span> <span className="num text-muted">{t.score.toFixed(2)}</span></span>
                    <blockquote className="border-s-2 border-accent-2 ps-2 text-sm text-muted" dir="auto">“{t.evidence_sentence}”</blockquote>
                    <Prov p={t} d={d} />
                  </li>
                ))}
              </ul>
            ) : <p className="text-sm text-muted">{d.article.noTargeted}</p>}
          </Panel>
        </div>
      </Section>

      <div className="grid gap-6 md:grid-cols-2">
        <Section title={d.article.mentions}>
          <Panel>
            <ul className="flex flex-wrap gap-2">
              {a.mentions.filter((m) => m.entity).map((m, i) => (
                <li key={i}>
                  <Link href={m.entity_type === "location" ? `/${l}/geography` : `/${l}/actors/${m.entity}`} title={m.framing_note ?? undefined}
                    className="inline-flex items-center gap-1 rounded-full border border-line px-2.5 py-0.5 text-sm hover:border-accent" dir="auto">
                    {m.surface_form}{m.alias_type && <span className="text-[0.65rem] text-muted">· {(d.aliasTypes as Record<string, string>)[m.alias_type] ?? m.alias_type}</span>}
                  </Link>
                </li>
              ))}
            </ul>
          </Panel>
        </Section>
        <Section title={d.article.events}>
          <Panel>
            {a.events.length ? (
              <ul className="flex flex-col gap-2 text-sm">
                {a.events.map((e) => (
                  <li key={e.id}><Link className="hover:underline font-medium" href={`/${l}/events?event=${e.id}`}>{e.type.replaceAll("_", " ")}</Link> · <span className="num">{fmtDate(e.date, l)}</span>
                    {e.evidence_sentence && <p className="text-muted" dir="auto">“{e.evidence_sentence}”</p>}</li>
                ))}
              </ul>
            ) : <p className="text-sm text-muted">{d.common.none}</p>}
          </Panel>
        </Section>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Section title={d.article.cluster}>
          <Panel>
            {a.story_cluster ? (
              <p className="text-sm">{d.article.clusterNote.replace("{n}", fmtNumber(a.story_cluster.article_count, l)).replace("{s}", fmtNumber(a.story_cluster.source_count, l)).replace("{i}", fmtNumber(a.story_cluster.independent_source_count, l))}</p>
            ) : <p className="text-sm text-muted">{d.common.none}</p>}
            {a.relations.length > 0 && (
              <ul className="mt-3 flex flex-col gap-1.5 text-sm">
                {a.relations.map((r) => (
                  <li key={`${r.type}-${r.article_id}`}><span className="text-xs text-muted font-mono">{r.type} {r.similarity?.toFixed(2)}</span> <Link className="hover:underline" href={`/${l}/news/${r.article_id}`} dir="auto">{r.title}</Link> <span className="text-muted">· {r.source}</span></li>
                ))}
              </ul>
            )}
          </Panel>
        </Section>
        <Section title={d.article.quality} note={d.article.qualityNote}>
          <Panel>
            <p className="text-sm num">{a.quality.score?.toFixed(2) ?? "–"} · {d.common.language}: {a.language.code} ({a.language.confidence?.toFixed(2)}, {a.language.method})</p>
          </Panel>
        </Section>
      </div>
    </article>
  );
}
