"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { LANG_NAMES, t } from "@/lib/modules";
import { CATEGORY_ORDER, COLLECTABLE, L, SCORE_TEXT } from "@/lib/registry";
import type { Dict, Locale } from "@/lib/i18n";

export interface Account { platform: string; handle: string; url: string; followers?: number | null; followers_as_of?: string | null }
export interface Src {
  slug: string; name: string; name_native: string | null; url: string; country: string | null; source_group: string;
  operating_base: string; languages: string[]; active: boolean; is_demo: boolean; health_status: string; feeds: number; articles: number;
  category: string; tier: string | null; region: string | null; platform: string | null; content_type: string;
  yemen_political_alignment: string; sub_alignment: string | null; regional_alignment: string; domestic_political_orientation: string | null;
  classification_confidence: number | null; influence_score: number | null; institutional_importance: string | null;
  reliability_score: number | null; selection_reason: string | null; holder: { role?: string } | null; accounts: Account[];
  orientation: { simplified: string; confidence: number; method: string; review_status?: string; evidence?: string | null;
    evidence_items?: { url: string; type: string }[] } | null;
}

const PAGE = 24;
const UI = {
  en: { cats: "Source categories", search: "Search sources", filters: "Filters", all: "All", tier: "Selection basis", region: "Region", camp: "Yemeni camp", regional: "Regional alignment",
    lang: "Language", collected: "Only sources collected now", showing: "sources", of: "of", sort: "Sort", sInf: "Influence", sName: "Name", sArt: "Articles",
    reset: "Clear filters", evidence: "evidence", draft: "draft, pending expert review", feeds: "feeds", noFeed: "not collected yet", none: "No source matches these filters.",
    open: "Open profile", xNote: "Listed, not collected: the X API requires paid configuration, and Facebook and Instagram are not collected.", legend: "● collected account", articles: "articles" },
  ar: { cats: "فئات المصادر", search: "ابحث في المصادر", filters: "التصفية", all: "الكل", tier: "أساس الاختيار", region: "المنطقة", camp: "المعسكر اليمني", regional: "الانحياز الإقليمي",
    lang: "اللغة", collected: "المصادر التي تُجمع حاليًا فقط", showing: "مصدرًا", of: "من", sort: "الترتيب", sInf: "التأثير", sName: "الاسم", sArt: "المقالات",
    reset: "مسح التصفية", evidence: "أدلة", draft: "مسودة بانتظار مراجعة الخبراء", feeds: "تغذيات", noFeed: "لا يُجمع بعد", none: "لا يوجد مصدر يطابق هذه التصفية.",
    open: "فتح الملف", xNote: "مسجل ولا يُجمع: واجهة إكس تتطلب إعدادًا مدفوعًا، ولا تُجمع حسابات فيسبوك وإنستغرام.", legend: "● حساب يُجمع", articles: "مقالة" },
};

function Facet({ title, children }: { title: string; children: React.ReactNode }) {
  return <fieldset className="flex flex-col gap-1.5 min-w-0"><legend className="label-caps text-muted mb-1">{title}</legend>{children}</fieldset>;
}

function Meter({ value }: { value: number }) {
  return (
    <span className="flex items-center gap-2 min-w-0">
      <span className="h-1.5 flex-1 min-w-12 rounded bg-surface-2" aria-hidden><span className="block h-1.5 rounded bg-accent-2" style={{ width: `${Math.max(2, value)}%` }} /></span>
      <span className="num text-xs">{Math.round(value)}</span>
    </span>
  );
}

export default function SourceRegistry({ sources, l, d }: { sources: Src[]; l: Locale; d: Dict }) {
  const u = UI[l], sc = SCORE_TEXT[l];
  const [cat, setCat] = useState<string>("");
  const [q, setQ] = useState("");
  const [tiers, setTiers] = useState<string[]>([]);
  const [regions, setRegions] = useState<string[]>([]);
  const [camps, setCamps] = useState<string[]>([]);
  const [regional, setRegional] = useState<string[]>([]);
  const [langs, setLangs] = useState<string[]>([]);
  const [collected, setCollected] = useState(false);
  const [sort, setSort] = useState<"influence" | "name" | "articles">("influence");
  const [page, setPage] = useState(0);
  const [showFacets, setShowFacets] = useState(false);

  const toggle = (set: (f: (a: string[]) => string[]) => void) => (v: string) => { set((a) => (a.includes(v) ? a.filter((x) => x !== v) : [...a, v])); setPage(0); };
  const inCat = useMemo(() => sources.filter((s) => !cat || s.category === cat), [sources, cat]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const r = inCat.filter((s) =>
      (!needle || s.name.toLowerCase().includes(needle) || (s.name_native ?? "").includes(needle) || s.url.toLowerCase().includes(needle)
        || (s.holder?.role ?? "").toLowerCase().includes(needle)) &&
      (!tiers.length || tiers.includes(s.tier ?? "")) && (!regions.length || regions.includes(s.region ?? "")) &&
      (!camps.length || camps.includes(s.yemen_political_alignment)) && (!regional.length || regional.includes(s.regional_alignment)) &&
      (!langs.length || s.languages.some((x) => langs.includes(x))) && (!collected || (s.active && s.feeds > 0)));
    r.sort((a, b) => sort === "articles" ? b.articles - a.articles
      : sort === "influence" ? (b.influence_score ?? -1) - (a.influence_score ?? -1) || a.name.localeCompare(b.name)
      : a.name.localeCompare(b.name));
    return r;
  }, [inCat, q, tiers, regions, camps, regional, langs, collected, sort]);

  const count = (key: (s: Src) => string | string[]) => {
    const m = new Map<string, number>();
    for (const s of inCat) for (const k of [key(s)].flat()) if (k) m.set(k, (m.get(k) ?? 0) + 1);
    return [...m.entries()].sort((a, b) => b[1] - a[1]);
  };
  const catCount = new Map<string, number>();
  for (const s of sources) catCount.set(s.category, (catCount.get(s.category) ?? 0) + 1);
  const tierC = count((s) => s.tier ?? ""), regionC = count((s) => s.region ?? ""), campC = count((s) => s.yemen_political_alignment),
    regionalC = count((s) => s.regional_alignment), langC = count((s) => s.languages);
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE));
  const view = filtered.slice(page * PAGE, page * PAGE + PAGE);
  const dirty = q || tiers.length || regions.length || camps.length || regional.length || langs.length || collected;
  const box = "flex items-center gap-2 text-sm cursor-pointer";
  const Check = ({ id, label, n, on, onChange }: { id: string; label: string; n: number; on: boolean; onChange: (v: string) => void }) => (
    <label className={box}><input type="checkbox" checked={on} onChange={() => onChange(id)} className="accent-[var(--accent)]" />
      <span className="flex-1 min-w-0 truncate">{label}</span><span className="text-xs text-muted num">{n}</span></label>
  );
  const tab = (key: string, label: string, n: number) => (
    <button key={key || "all"} type="button" onClick={() => { setCat(key); setPage(0); }} aria-pressed={cat === key}
      className={`shrink-0 rounded-full border px-3 py-1 text-sm ${cat === key ? "border-accent bg-accent text-accent-ink" : "border-line bg-surface hover:border-accent-2"}`}>
      {label} <span className="num opacity-75">{n}</span>
    </button>
  );

  return (
    <div className="flex flex-col gap-5">
      <nav aria-label={u.cats} className="flex gap-2 overflow-x-auto pb-1 -mx-1 px-1">
        {tab("", u.all, sources.length)}
        {CATEGORY_ORDER.filter((k) => catCount.get(k)).map((k) => tab(k, L.category(k, l), catCount.get(k) ?? 0))}
      </nav>
      <div className="grid gap-6 lg:grid-cols-[17rem_1fr] items-start">
        <aside className="rounded-lg border border-line bg-surface p-4 flex flex-col gap-5 lg:sticky lg:top-36 lg:max-h-[calc(100vh-10rem)] lg:overflow-y-auto">
          <input type="search" value={q} onChange={(e) => { setQ(e.target.value); setPage(0); }} placeholder={u.search} aria-label={u.search}
            className="w-full rounded-md border border-line bg-bg px-3 py-1.5 text-sm" />
          <button type="button" aria-expanded={showFacets} onClick={() => setShowFacets((v) => !v)}
            className="lg:hidden text-sm font-medium text-accent-2 text-start">{u.filters} {showFacets ? "▴" : "▾"}</button>
          <div className={`${showFacets ? "flex" : "hidden"} lg:flex flex-col gap-5`}>
            <Facet title={u.tier}>{tierC.map(([k, n]) => <Check key={k} id={k} n={n} label={L.tier(k, l)} on={tiers.includes(k)} onChange={toggle(setTiers)} />)}</Facet>
            <Facet title={u.camp}>{campC.map(([k, n]) => <Check key={k} id={k} n={n} label={L.yemen(k, l)} on={camps.includes(k)} onChange={toggle(setCamps)} />)}</Facet>
            <Facet title={u.regional}>{regionalC.map(([k, n]) => <Check key={k} id={k} n={n} label={L.regional(k, l)} on={regional.includes(k)} onChange={toggle(setRegional)} />)}</Facet>
            <Facet title={u.region}>{regionC.map(([k, n]) => <Check key={k} id={k} n={n} label={L.region(k, l)} on={regions.includes(k)} onChange={toggle(setRegions)} />)}</Facet>
            <Facet title={u.lang}>{langC.map(([k, n]) => <Check key={k} id={k} n={n} label={LANG_NAMES[k] ? t(LANG_NAMES[k], l) : k.toUpperCase()} on={langs.includes(k)} onChange={toggle(setLangs)} />)}</Facet>
            <label className={box}><input type="checkbox" checked={collected} onChange={(e) => { setCollected(e.target.checked); setPage(0); }} className="accent-[var(--accent)]" />{u.collected}</label>
          </div>
          {dirty ? <button type="button" className="text-sm text-accent-2 text-start" onClick={() => { setQ(""); setTiers([]); setRegions([]); setCamps([]); setRegional([]); setLangs([]); setCollected(false); setPage(0); }}>{u.reset}</button> : null}
        </aside>

        <div className="flex flex-col gap-3 min-w-0">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm"><span className="num font-semibold">{filtered.length}</span> <span className="text-muted">{u.of} <span className="num">{inCat.length}</span> {u.showing}</span></p>
            <label className="flex items-center gap-2 text-sm text-muted">{u.sort}
              <select value={sort} onChange={(e) => setSort(e.target.value as typeof sort)} className="rounded-md border border-line bg-surface px-2 py-1 text-sm text-ink">
                <option value="influence">{u.sInf}</option><option value="name">{u.sName}</option><option value="articles">{u.sArt}</option></select></label>
          </div>
          <p className="text-xs text-muted max-w-3xl">{sc.note} <span className="text-accent-2">{u.legend}</span>. {u.xNote}</p>
          {view.length === 0 && <p className="py-10 text-center text-muted">{u.none}</p>}
          <ul className="flex flex-col gap-2">
            {view.map((s) => {
              const ev = s.orientation?.evidence_items ?? [];
              const camp = !["unknown", "not_applicable", "none_documented"].includes(s.yemen_political_alignment) ? s.yemen_political_alignment : null;
              const reg = !["unknown", "not_applicable", "none_documented"].includes(s.regional_alignment) ? s.regional_alignment : null;
              const noneDoc = s.yemen_political_alignment === "none_documented" || s.regional_alignment === "none_documented";
              return (
                <li key={s.slug} className="rounded-lg border border-line bg-surface p-4 grid gap-x-6 gap-y-3 md:grid-cols-[minmax(0,5fr)_minmax(0,3fr)] xl:grid-cols-[minmax(0,5fr)_minmax(0,3fr)_minmax(0,3fr)] items-start">
                  <div className="min-w-0 flex flex-col gap-1">
                    <div className="flex flex-wrap items-baseline gap-x-2">
                      <Link href={`/${l}/sources/${s.slug}`} className="font-semibold hover:underline" aria-label={`${u.open}: ${s.name}`}>{s.name}</Link>
                      {s.name_native && <bdi className="text-sm text-muted">{s.name_native}</bdi>}
                    </div>
                    <span className="text-xs text-muted">{L.category(s.category, l)}{s.region ? ` · ${L.region(s.region, l)}` : ""}{s.country ? ` · ${s.country}` : ""}{s.tier ? ` · ${L.tier(s.tier, l)}` : ""}</span>
                    {s.holder?.role && <span className="text-sm">{s.holder.role}</span>}
                    {s.selection_reason && <p className="text-sm text-muted line-clamp-2">{s.selection_reason}</p>}
                    {s.is_demo && <span className="self-start rounded px-1.5 py-0.5 text-[0.68rem] font-semibold bg-demo-bg text-demo border border-demo/40">{d.site.demoBadge}</span>}
                  </div>
                  <dl className="min-w-0 grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1.5 text-xs items-center">
                    <dt className="text-muted">{sc.influence}</dt>
                    <dd className="min-w-0">{s.influence_score !== null ? <Meter value={s.influence_score} /> : <span className="text-muted">{sc.notScored}</span>}</dd>
                    <dt className="text-muted">{sc.institutional}</dt>
                    <dd>{s.institutional_importance ? L.level(s.institutional_importance, l) : "–"}</dd>
                    <dt className="text-muted">{sc.reliability}</dt>
                    <dd className="text-muted">{s.reliability_score !== null ? s.reliability_score.toFixed(2) : sc.notAssessed}</dd>
                  </dl>
                  <div className="min-w-0 flex flex-col gap-1.5 text-xs md:col-span-2 xl:col-span-1">
                    <div className="flex flex-wrap items-center gap-1.5">
                      {camp && <span className="rounded-full border border-accent-2 text-accent-2 px-2 py-0.5">{L.yemen(camp, l)}</span>}
                      {reg && <span className="rounded-full border border-line px-2 py-0.5">{L.regional(reg, l)}</span>}
                      {!camp && !reg && <span className="rounded-full border border-line text-muted px-2 py-0.5">{L.yemen(noneDoc ? "none_documented" : "unknown", l)}</span>}
                      {s.classification_confidence !== null && (camp || reg) && <span className="num text-muted">{s.classification_confidence.toFixed(2)}</span>}
                      {ev.length > 0 && <a href={ev[0].url} target="_blank" rel="noopener noreferrer" className="text-accent-2 hover:underline">{ev.length} {u.evidence} ↗</a>}
                    </div>
                    {(camp || reg) && s.orientation?.review_status && s.orientation.review_status !== "reviewed" && <span className="text-[0.7rem] text-muted">{u.draft}</span>}
                    {s.accounts.length > 0 && (
                      <div className="flex flex-wrap gap-1">{s.accounts.map((a) => (
                        <a key={a.url} href={a.url} target="_blank" rel="noopener noreferrer" title={COLLECTABLE.has(a.platform) ? undefined : u.xNote}
                          className={`rounded border px-1.5 py-0.5 ${COLLECTABLE.has(a.platform) ? "border-accent-2/50" : "border-line text-muted"}`}>
                          {COLLECTABLE.has(a.platform) && <span aria-hidden className="text-accent-2">● </span>}{L.platform(a.platform, l)} @{a.handle}</a>))}</div>
                    )}
                    <span className="text-muted">{s.active && s.feeds ? `${s.feeds} ${u.feeds} · ${s.health_status}` : u.noFeed} · <span className="num">{s.articles}</span> {u.articles}</span>
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
    </div>
  );
}
