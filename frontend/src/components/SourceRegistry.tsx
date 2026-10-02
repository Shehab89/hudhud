"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { GROUP_LABELS, LANG_NAMES, ORIENT_LABELS, t } from "@/lib/modules";
import type { Dict, Locale } from "@/lib/i18n";

export interface Src {
  slug: string; name: string; name_native: string | null; url: string; country: string | null; source_group: string;
  operating_base: string; languages: string[]; active: boolean; is_demo: boolean; health_status: string; feeds: number; articles: number;
  orientation: { simplified: string; confidence: number; method: string; review_status?: string; evidence?: string | null;
    evidence_items?: { url: string; type: string }[] } | null;
}

const PAGE = 24;
const UI = {
  en: { search: "Search outlets", filters: "Filters", group: "Source group", base: "Newsroom location", lang: "Language", orient: "Orientation label", evOnly: "Only with cited evidence",
    inactive: "Include outlets with no working feed", showing: "outlets", of: "of", sort: "Sort", sName: "Name", sArt: "Articles", sConf: "Confidence", reset: "Clear filters",
    evidence: "evidence", draft: "draft, pending expert review", feeds: "feeds", noFeed: "no feed", none: "No outlet matches these filters.", open: "Open profile",
    note: "Orientation describes ownership, funding and documented alignment. It is not a rating of accuracy or reliability, and “not assessed” means no public evidence has been recorded yet." },
  ar: { search: "ابحث في المنافذ", filters: "التصفية", group: "مجموعة المصدر", base: "موقع غرفة الأخبار", lang: "اللغة", orient: "وصف التوجه", evOnly: "فقط ما له أدلة موثقة",
    inactive: "تضمين المنافذ بلا تغذية عاملة", showing: "منفذًا", of: "من", sort: "الترتيب", sName: "الاسم", sArt: "المقالات", sConf: "الثقة", reset: "مسح التصفية",
    evidence: "أدلة", draft: "مسودة بانتظار مراجعة الخبراء", feeds: "تغذيات", noFeed: "بلا تغذية", none: "لا يوجد منفذ يطابق هذه التصفية.", open: "فتح الملف",
    note: "يصف التوجه الملكية والتمويل والانحياز الموثق، وليس تقييمًا للدقة أو الموثوقية. «غير مقيَّم» يعني أنه لم تُسجَّل أدلة علنية بعد." },
};

function Facet({ title, children }: { title: string; children: React.ReactNode }) {
  return <fieldset className="flex flex-col gap-1.5 min-w-0"><legend className="label-caps text-muted mb-1">{title}</legend>{children}</fieldset>;
}

export default function SourceRegistry({ sources, l, d }: { sources: Src[]; l: Locale; d: Dict }) {
  const u = UI[l];
  const [q, setQ] = useState("");
  const [groups, setGroups] = useState<string[]>([]);
  const [bases, setBases] = useState<string[]>([]);
  const [langs, setLangs] = useState<string[]>([]);
  const [orient, setOrient] = useState<string[]>([]);
  const [evOnly, setEvOnly] = useState(false);
  const [inactive, setInactive] = useState(true);
  const [sort, setSort] = useState<"name" | "articles" | "confidence">("name");
  const [page, setPage] = useState(0);
  const [showFacets, setShowFacets] = useState(false);

  const orientOf = (s: Src) => s.orientation?.simplified ?? "unknown";
  const hasEv = (s: Src) => (s.orientation?.evidence_items?.length ?? 0) > 0;
  const toggle = (set: (f: (a: string[]) => string[]) => void) => (v: string) => { set((a) => (a.includes(v) ? a.filter((x) => x !== v) : [...a, v])); setPage(0); };

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const r = sources.filter((s) =>
      (!needle || s.name.toLowerCase().includes(needle) || (s.name_native ?? "").includes(needle) || s.url.toLowerCase().includes(needle)) &&
      (!groups.length || groups.includes(s.source_group)) && (!bases.length || bases.includes(s.operating_base)) &&
      (!langs.length || s.languages.some((x) => langs.includes(x))) && (!orient.length || orient.includes(orientOf(s))) &&
      (!evOnly || hasEv(s)) && (inactive || s.feeds > 0));
    r.sort((a, b) => sort === "articles" ? b.articles - a.articles : sort === "confidence" ? (b.orientation?.confidence ?? 0) - (a.orientation?.confidence ?? 0) : a.name.localeCompare(b.name));
    return r;
  }, [sources, q, groups, bases, langs, orient, evOnly, inactive, sort]);

  const count = (key: (s: Src) => string | string[]) => {
    const m = new Map<string, number>();
    for (const s of sources) for (const k of [key(s)].flat()) m.set(k, (m.get(k) ?? 0) + 1);
    return [...m.entries()].sort((a, b) => b[1] - a[1]);
  };
  const groupC = count((s) => s.source_group), baseC = count((s) => s.operating_base), langC = count((s) => s.languages), orientC = count(orientOf);
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE));
  const view = filtered.slice(page * PAGE, page * PAGE + PAGE);
  const dirty = q || groups.length || bases.length || langs.length || orient.length || evOnly;
  const box = "flex items-center gap-2 text-sm cursor-pointer";
  const Check = ({ id, label, n, on, onChange }: { id: string; label: string; n: number; on: boolean; onChange: (v: string) => void }) => (
    <label className={box}><input type="checkbox" checked={on} onChange={() => onChange(id)} className="accent-[var(--accent)]" />
      <span className="flex-1 min-w-0 truncate">{label}</span><span className="text-xs text-muted num">{n}</span></label>
  );

  return (
    <div className="grid gap-6 lg:grid-cols-[17rem_1fr] items-start">
      <aside className="rounded-lg border border-line bg-surface p-4 flex flex-col gap-5 lg:sticky lg:top-36 lg:max-h-[calc(100vh-10rem)] lg:overflow-y-auto">
        <input type="search" value={q} onChange={(e) => { setQ(e.target.value); setPage(0); }} placeholder={u.search} aria-label={u.search}
          className="w-full rounded-md border border-line bg-bg px-3 py-1.5 text-sm" />
        <button type="button" aria-expanded={showFacets} onClick={() => setShowFacets((v) => !v)}
          className="lg:hidden text-sm font-medium text-accent-2 text-start">{u.filters} {showFacets ? "▴" : "▾"}</button>
        <div className={`${showFacets ? "flex" : "hidden"} lg:flex flex-col gap-5`}>
        <Facet title={u.orient}>{orientC.map(([k, n]) => <Check key={k} id={k} n={n} label={t(ORIENT_LABELS[k] ?? { en: k, ar: k }, l)} on={orient.includes(k)} onChange={toggle(setOrient)} />)}</Facet>
        <Facet title={u.group}>{groupC.map(([k, n]) => <Check key={k} id={k} n={n} label={t(GROUP_LABELS[k] ?? { en: k.replaceAll("_", " "), ar: k }, l)} on={groups.includes(k)} onChange={toggle(setGroups)} />)}</Facet>
        <Facet title={u.base}>{baseC.map(([k, n]) => <Check key={k} id={k} n={n} label={(d.bases as Record<string, string>)[k] ?? k} on={bases.includes(k)} onChange={toggle(setBases)} />)}</Facet>
        <Facet title={u.lang}>{langC.map(([k, n]) => <Check key={k} id={k} n={n} label={LANG_NAMES[k] ? t(LANG_NAMES[k], l) : k.toUpperCase()} on={langs.includes(k)} onChange={toggle(setLangs)} />)}</Facet>
        <label className={box}><input type="checkbox" checked={evOnly} onChange={(e) => { setEvOnly(e.target.checked); setPage(0); }} className="accent-[var(--accent)]" />{u.evOnly}</label>
        <label className={box}><input type="checkbox" checked={inactive} onChange={(e) => { setInactive(e.target.checked); setPage(0); }} className="accent-[var(--accent)]" />{u.inactive}</label>
        </div>
        {dirty ? <button type="button" className="text-sm text-accent-2 text-start" onClick={() => { setQ(""); setGroups([]); setBases([]); setLangs([]); setOrient([]); setEvOnly(false); setPage(0); }}>{u.reset}</button> : null}
      </aside>

      <div className="flex flex-col gap-3 min-w-0">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm"><span className="num font-semibold">{filtered.length}</span> <span className="text-muted">{u.of} <span className="num">{sources.length}</span> {u.showing}</span></p>
          <label className="flex items-center gap-2 text-sm text-muted">{u.sort}
            <select value={sort} onChange={(e) => setSort(e.target.value as typeof sort)} className="rounded-md border border-line bg-surface px-2 py-1 text-sm text-ink">
              <option value="name">{u.sName}</option><option value="articles">{u.sArt}</option><option value="confidence">{u.sConf}</option></select></label>
        </div>
        <p className="text-xs text-muted max-w-3xl">{u.note}</p>
        {view.length === 0 && <p className="py-10 text-center text-muted">{u.none}</p>}
        <ul className="flex flex-col gap-2">
          {view.map((s) => {
            const o = s.orientation, k = orientOf(s), ev = o?.evidence_items ?? [];
            return (
              <li key={s.slug} className="rounded-lg border border-line bg-surface p-4 grid gap-x-6 gap-y-2 md:grid-cols-[minmax(0,2fr)_minmax(0,2fr)_auto] items-start">
                <div className="min-w-0">
                  <Link href={`/${l}/sources/${s.slug}`} className="font-semibold hover:underline" aria-label={`${u.open}: ${s.name}`}>{s.name}</Link>
                  {s.name_native && <span className="block text-sm text-muted"><bdi>{s.name_native}</bdi></span>}
                  <span className="block text-xs text-muted mt-1">{t(GROUP_LABELS[s.source_group] ?? { en: s.source_group, ar: s.source_group }, l)}{s.country ? ` · ${s.country}` : ""}</span>
                  {s.is_demo && <span className="mt-1 inline-block rounded px-1.5 py-0.5 text-[0.68rem] font-semibold bg-demo-bg text-demo border border-demo/40">{d.site.demoBadge}</span>}
                </div>
                <div className="min-w-0 flex flex-col gap-1.5 text-sm">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className={`rounded-full border px-2 py-0.5 text-xs ${k === "unknown" ? "border-line text-muted" : "border-accent-2 text-accent-2"}`}>{t(ORIENT_LABELS[k] ?? { en: k, ar: k }, l)}</span>
                    {o && k !== "unknown" && <span className="text-xs text-muted num" title={o.method}>{o.confidence.toFixed(2)}</span>}
                    {ev.length > 0 && (
                      <a href={ev[0].url} target="_blank" rel="noopener noreferrer" className="text-xs text-accent-2 hover:underline">{ev.length} {u.evidence} ↗</a>)}
                  </div>
                  {o && k !== "unknown" && o.review_status && o.review_status !== "reviewed" && <span className="text-[0.7rem] text-muted">{u.draft}</span>}
                  <div className="flex flex-wrap gap-1">{s.languages.map((x) => <span key={x} className="rounded bg-surface-2 px-1.5 py-0.5 text-[0.7rem] uppercase">{x}</span>)}</div>
                </div>
                <div className="text-xs text-muted flex md:flex-col md:items-end gap-x-4 gap-y-0.5 flex-wrap">
                  <span>{(d.bases as Record<string, string>)[s.operating_base] ?? s.operating_base}</span>
                  <span>{s.feeds ? `${s.feeds} ${u.feeds} · ${s.health_status}` : u.noFeed}</span>
                  <span className="num">{s.articles} {d.common.articles.toLowerCase()}</span>
                </div>
              </li>
            );
          })}
        </ul>
        {pages > 1 && (
          <nav aria-label="Pagination" className="flex items-center justify-center gap-3 pt-2 text-sm">
            <button type="button" disabled={page === 0} onClick={() => setPage(page - 1)} className="rounded-md border border-line px-3 py-1.5 disabled:opacity-40">{d.common.prev}</button>
            <span className="num text-muted">{d.common.page} {page + 1} {d.common.of} {pages}</span>
            <button type="button" disabled={page >= pages - 1} onClick={() => setPage(page + 1)} className="rounded-md border border-line px-3 py-1.5 disabled:opacity-40">{d.common.next}</button>
          </nav>
        )}
      </div>
    </div>
  );
}
