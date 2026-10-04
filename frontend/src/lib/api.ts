/** Typed access to the FastAPI backend. Server components call it directly; nothing secret is sent. */

export const API_URL = (process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");
export const PUBLIC_API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export type SearchParams = Record<string, string | string[] | undefined>;

export const FILTER_KEYS = ["date_from", "date_to", "language", "source", "source_group", "operating_base", "category", "entity", "demo",
  "source_category", "source_tier", "source_region", "source_country", "yemen_alignment", "regional_alignment", "content_type"] as const;

export function filterQuery(sp: SearchParams, extra: Record<string, string | number | undefined> = {}) {
  const q = new URLSearchParams();
  for (const k of FILTER_KEYS) {
    const v = sp[k];
    if (Array.isArray(v)) v.forEach((x) => x && q.append(k, x));
    else if (v) q.set(k, v);
  }
  for (const [k, v] of Object.entries(extra)) if (v !== undefined && v !== "") q.set(k, String(v));
  const s = q.toString();
  return s ? `?${s}` : "";
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function api<T>(path: string, init?: { revalidate?: number }): Promise<T> {
  const res = await fetch(`${API_URL}/api/v1${path}`, {
    next: { revalidate: init?.revalidate ?? 300 },
    headers: { Accept: "application/json" },
  });
  if (!res.ok) throw new ApiError(res.status, `${res.status} ${path}`);
  return res.json() as Promise<T>;
}

/** Like api() but returns null instead of throwing, so one failed panel never breaks a page. */
export async function tryApi<T>(path: string, init?: { revalidate?: number }): Promise<T | null> {
  try {
    return await api<T>(path, init);
  } catch {
    return null;
  }
}

// ---- response types (subset of the OpenAPI contract the UI uses)

export interface SourceRef { slug: string; name: string; source_group: string; operating_base: string; country: string | null; is_demo: boolean;
  category?: string; tier?: string | null; content_type?: string; region?: string | null }

export interface ArticleSummary {
  id: number; title: string; url: string; published_at: string | null; language: string | null; excerpt: string | null;
  source: SourceRef; publisher_name: string | null; is_demo: boolean; is_syndicated: boolean;
  story_cluster_id: number | null; primary_category: string | null; sentiment: string | null;
}

export interface Paged<T> { total: number; limit: number; offset: number; items: T[]; contains_demo: boolean }

export interface Kpis { articles: number; unique_stories: number; sources_active: number; languages: number; demo_articles: number; events: number; actors_mentioned: number }

export interface Overview {
  filters: Record<string, unknown>; current: Kpis; previous: Kpis; contains_demo: boolean;
  summary: Record<string, { day: string; content: string; method: string }>;
  last_pipeline_run: { id: number; status: string; started_at: string; finished_at: string | null } | null;
}

export interface Timeline { split: string; days: string[]; keys: string[]; series: Record<string, number[]> }

export interface Trend {
  id: number; slug: string | null; label: string; label_ar: string | null; frequency: number; previous: number;
  growth_rate: number; acceleration: number; source_count: number; source_diversity: number | null;
  language_count: number; status: "emerging" | "declining" | "stable"; series: [string, number][];
}

export interface Prov { method: string; model: string | null; model_version: string | null; confidence: number | null; analysis_version: string | null }

export interface ArticleDetail {
  id: number; is_demo: boolean; title: string; url: string; canonical_url: string; excerpt: string | null;
  published_at: string | null; published_at_estimated: boolean; author: string | null; publisher_name: string | null;
  language: { code: string | null; confidence: number | null; script: string | null; mixed: boolean; method: string | null };
  quality: { score: number | null; detail: Record<string, number>; note: string };
  source: { slug: string; name: string; source_group: string; operating_base: string; is_demo: boolean;
    category?: string; tier?: string | null; content_type?: string; yemen_political_alignment?: string; regional_alignment?: string;
    orientation: { simplified: string; confidence: number; method: string } | null };
  sentiment: (Prov & { polarity: string; scores: Record<string, number>; intensity: number | null })[];
  emotions: (Prov & { kind: string; dominant: string | null; scores: Record<string, number> })[];
  categories: (Prov & { slug: string; name_en: string; name_ar: string | null; rank: string; score: number; route: string | null; evidence: Record<string, unknown> })[];
  frames: (Prov & { slug: string; name_en: string; name_ar: string | null; score: number; evidence_sentence: string | null })[];
  targeted_sentiment: (Prov & { entity: string | null; entity_name: string | null; sentiment: string; score: number; evidence_sentence: string })[];
  mentions: { entity: string | null; entity_type: string | null; surface_form: string; field: string; start: number | null; end: number | null; alias_type: string | null; framing_note: string | null; method: string }[];
  events: { id: number; type: string; date: string; title: string | null; confidence: number; evidence_sentence: string | null; trigger: string | null }[];
  topics: { id: number; label: string; scope: string; probability: number | null }[];
  relations: { type: string; similarity: number | null; method: string; article_id: number; title: string; source: string; is_demo: boolean }[];
  story_cluster: { id: number; article_count: number; source_count: number; independent_source_count: number; language_count: number } | null;
  duplicate_of_id: number | null; is_syndicated: boolean; processing_status: string;
}

export interface Meta {
  analysis_version: string;
  languages: { code: string; name: string; name_native: string | null; rtl: boolean }[];
  source_groups: string[]; operating_bases: string[];
  frames: { slug: string; name_en: string; name_ar: string | null; description: string | null }[];
  event_types: string[]; entity_types: string[]; routing_thresholds: { accept: number; secondary_model: number };
  llm_enabled: boolean; has_demo_data: boolean; data_range: { first: string | null; last: string | null };
}
