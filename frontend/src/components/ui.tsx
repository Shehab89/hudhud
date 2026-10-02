import Link from "next/link";
import type { ReactNode } from "react";
import type { Dict, Locale } from "@/lib/i18n";
import { fmtNumber } from "@/lib/i18n";

export const BASE_COLORS: Record<string, string> = {
  sanaa_controlled: "var(--base-sanaa)",
  government_controlled: "var(--base-gov)",
  stc_controlled: "var(--base-stc)",
  outside_yemen: "var(--base-outside)",
  unknown: "var(--base-unknown)",
};

export const SENTIMENT_COLORS: Record<string, string> = {
  negative: "var(--neg)", neutral: "var(--neu)", positive: "var(--pos)", uncertain: "var(--unc)", not_analysed: "var(--line)",
};

export function PageHeader({ title, intro, children }: { title: string; intro?: string; children?: ReactNode }) {
  return (
    <header className="flex flex-col gap-3 pb-6 border-b border-line mb-6">
      <h1 className="text-2xl md:text-3xl font-semibold tracking-tight">{title}</h1>
      {intro && <p className="text-muted max-w-3xl leading-relaxed">{intro}</p>}
      {children}
    </header>
  );
}

export function Section({ title, note, action, children, className = "" }: {
  title: string; note?: string; action?: ReactNode; children: ReactNode; className?: string;
}) {
  return (
    <section className={`flex flex-col gap-3 min-w-0 ${className}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-semibold">{title}</h2>
        {action}
      </div>
      {note && <p className="text-sm text-muted -mt-2 max-w-3xl">{note}</p>}
      {children}
    </section>
  );
}

export function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-lg border border-line bg-surface p-4 min-w-0 ${className}`}>{children}</div>;
}

export function DemoBadge({ d }: { d: Dict }) {
  return (
    <span className="inline-flex items-center rounded px-1.5 py-0.5 text-[0.68rem] font-semibold tracking-wide bg-demo-bg text-demo border border-demo/40">
      {d.site.demoBadge}
    </span>
  );
}

export function BaseBadge({ base, d }: { base: string; d: Dict }) {
  const label = (d.bases as Record<string, string>)[base] ?? base;
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-muted">
      <span aria-hidden className="inline-block size-2 rounded-full" style={{ background: BASE_COLORS[base] ?? BASE_COLORS.unknown }} />
      {label}
    </span>
  );
}

export function SentimentBadge({ value, d }: { value: string | null; d: Dict }) {
  if (!value) return null;
  const label = (d.sentiment as Record<string, string>)[value] ?? value;
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-line px-2 py-0.5 text-xs">
      <span aria-hidden className="inline-block size-1.5 rounded-full" style={{ background: SENTIMENT_COLORS[value] }} />
      {label}
    </span>
  );
}

export function Kpi({ label, value, previous, l, d }: { label: string; value: number; previous?: number; l: Locale; d: Dict }) {
  const delta = previous !== undefined && previous > 0 ? (value - previous) / previous : null;
  return (
    <div className="flex flex-col gap-1 py-3 px-4 min-w-0">
      <span className="label-caps text-muted">{label}</span>
      <span className="text-2xl md:text-3xl font-semibold num">{fmtNumber(value, l)}</span>
      {delta !== null && (
        <span className="text-xs text-muted num">
          {delta >= 0 ? "▲" : "▼"} {fmtNumber(Math.abs(delta), l, { style: "percent", maximumFractionDigits: 0 })} {d.common.previous}
        </span>
      )}
    </div>
  );
}

export function Empty({ d }: { d: Dict }) {
  return <p className="text-sm text-muted py-6">{d.common.noData}</p>;
}

export function TextLink({ href, children }: { href: string; children: ReactNode }) {
  return <Link href={href} className="text-accent-2 hover:underline underline-offset-2">{children}</Link>;
}

export function Bar({ value, max, color = "var(--accent-2)" }: { value: number; max: number; color?: string }) {
  const w = max > 0 ? Math.max(2, (value / max) * 100) : 0;
  return (
    <div className="h-1.5 w-full rounded bg-surface-2" aria-hidden>
      <div className="h-1.5 rounded" style={{ width: `${w}%`, background: color }} />
    </div>
  );
}

export function Prov({ p, d }: { p: { method: string; model: string | null; model_version: string | null; confidence: number | null }; d: Dict }) {
  return (
    <span className="text-[0.7rem] text-muted font-mono break-all">
      {d.common.method}: {p.method}
      {p.model ? ` · ${p.model}${p.model_version ? `@${p.model_version}` : ""}` : ""}
      {p.confidence !== null && p.confidence !== undefined ? ` · ${d.common.confidence} ${p.confidence.toFixed(2)}` : ""}
    </span>
  );
}
