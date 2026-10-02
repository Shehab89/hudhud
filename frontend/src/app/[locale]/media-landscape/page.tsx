import type { EChartsOption } from "echarts";
import Link from "next/link";
import EChart from "@/components/EChart";
import FilterBar from "@/components/FilterBar";
import { BASE_COLORS, Empty, PageHeader, Panel, SENTIMENT_COLORS, Section } from "@/components/ui";
import { filterQuery, tryApi } from "@/lib/api";
import { fmtNumber, pick } from "@/lib/i18n";
import { one, setup, type PageProps } from "@/lib/page";

export const metadata = { title: "Media landscape" };

interface Graph { note: string; nodes: { id: string; name: string; operating_base: string; articles: number; is_demo: boolean }[];
  edges: { source: string; target: string; type: string; shared_stories?: number; jaccard?: number; articles?: number }[] }
interface Narr { groups: Record<string, { articles: number; frames: Record<string, number>; sentiment: Record<string, number>; tone: Record<string, number>;
  terminology: { entity: string; term: string; alias_type: string; mentions: number }[]; actors: { slug: string; name_en: string; share: number; mean_targeted_sentiment: number | null }[] }>;
  frames: Record<string, { name_en: string; name_ar: string | null }>; note: string }

export default async function Landscape(props: PageProps) {
  const { l, d, sp } = await setup(props);
  const groupBy = one(sp.group_by) || "operating_base";
  const [g, n] = await Promise.all([
    tryApi<Graph>(`/media-landscape${filterQuery(sp)}`),
    tryApi<Narr>(`/compare/narratives${filterQuery(sp, { group_by: groupBy })}`),
  ]);
  const bases = d.bases as Record<string, string>;
  const groupLabel = (k: string) => (groupBy === "operating_base" ? bases[k] ?? k : k);
  const maxA = Math.max(1, ...(g?.nodes ?? []).map((x) => x.articles));
  const option: EChartsOption | null = g && g.nodes.length ? {
    tooltip: {},
    legend: { data: Object.keys(BASE_COLORS).map((k) => bases[k]) },
    series: [{
      type: "graph", layout: "force", roam: true, draggable: true,
      force: { repulsion: 220, edgeLength: [60, 200], gravity: 0.08 },
      categories: Object.keys(BASE_COLORS).map((k) => ({ name: bases[k], itemStyle: { color: BASE_COLORS[k] } })),
      label: { show: true, position: "right", color: "var(--ink)", fontSize: 11 },
      data: g.nodes.map((x) => ({ id: x.id, name: x.name, value: x.articles, category: Object.keys(BASE_COLORS).indexOf(x.operating_base),
        symbolSize: 10 + 30 * Math.sqrt(x.articles / maxA) })),
      links: g.edges.map((e) => ({ source: e.source, target: e.target, value: e.shared_stories ?? e.articles,
        lineStyle: e.type === "syndication" ? { type: "dashed", color: "var(--accent)", width: 2 } : { color: "var(--line)", width: 1 + 6 * (e.jaccard ?? 0), opacity: 0.8 } })),
    }],
  } : null;
  const keys = n ? Object.keys(n.groups) : [];
  const frameKeys = n ? Object.keys(n.frames).filter((f) => keys.some((k) => (n.groups[k].frames[f] ?? 0) > 0)) : [];
  const pct = (v: number | undefined) => (v ? `${Math.round(v * 100)}%` : "–");
  return (
    <>
      <PageHeader title={d.landscape.title} intro={d.landscape.intro} />
      <FilterBar d={d} sp={sp} keep={["group_by"]} />
      <Panel className="mb-10">{option ? <EChart ariaLabel={d.landscape.title} height={520} option={option} /> : <Empty d={d} />}</Panel>

      <Section title={d.landscape.narratives} note={`${d.landscape.narrativesIntro} ${n?.note ?? ""}`}
        action={<nav className="flex gap-2 text-sm">{d.landscape.groupBy}: {["operating_base", "source_group", "language"].map((k) => (
          <Link key={k} href={`?${new URLSearchParams({ ...Object.fromEntries(Object.entries(sp).map(([a, b]) => [a, one(b)])), group_by: k })}`} className={groupBy === k ? "font-semibold text-accent" : "text-accent-2"}>{k.replaceAll("_", " ")}</Link>))}</nav>}>
        {n && keys.length ? (
          <Panel className="!p-0 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-xs text-muted"><th className="text-start p-2">{d.landscape.shares}</th>
                  {keys.map((k) => <th key={k} className="text-end p-2">{groupLabel(k)}<span className="block num">{fmtNumber(n.groups[k].articles, l)}</span></th>)}</tr>
              </thead>
              <tbody>
                {frameKeys.map((f) => (
                  <tr key={f} className="border-b border-line"><td className="p-2">{pick(l, n.frames[f].name_en, n.frames[f].name_ar)}</td>
                    {keys.map((k) => <td key={k} className="p-2 text-end num">{pct(n.groups[k].frames[f])}</td>)}</tr>
                ))}
                {["negative", "neutral", "positive"].map((s) => (
                  <tr key={s} className="border-b border-line"><td className="p-2"><span className="inline-block size-2 rounded-full me-1.5" style={{ background: SENTIMENT_COLORS[s] }} />{(d.sentiment as Record<string, string>)[s]}</td>
                    {keys.map((k) => <td key={k} className="p-2 text-end num">{pct(n.groups[k].sentiment[s])}</td>)}</tr>
                ))}
                <tr><td className="p-2 align-top">{d.common.terminology}</td>
                  {keys.map((k) => <td key={k} className="p-2 text-end align-top text-xs" dir="auto">{n.groups[k].terminology.slice(0, 5).map((t) => <div key={t.term}>{t.term} <span className="text-muted">({t.mentions})</span></div>)}</td>)}</tr>
              </tbody>
            </table>
          </Panel>
        ) : <Empty d={d} />}
      </Section>
    </>
  );
}
