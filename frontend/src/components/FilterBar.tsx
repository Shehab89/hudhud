import type { SearchParams } from "@/lib/api";
import type { Dict } from "@/lib/i18n";

const LANGS = ["ar", "en", "fr", "de", "es", "ru", "tr", "fa", "zh", "it", "he", "ur"];
const BASES = ["sanaa_controlled", "government_controlled", "stc_controlled", "outside_yemen", "unknown"];

/** Plain GET form: works without JavaScript and keeps every filter in the URL (shareable, citable). */
export default function FilterBar({ d, sp, keep = [], showDemo = true }: {
  d: Dict; sp: SearchParams; keep?: string[]; showDemo?: boolean;
}) {
  const v = (k: string) => (Array.isArray(sp[k]) ? (sp[k] as string[])[0] : (sp[k] as string | undefined)) ?? "";
  const field = "rounded-md border border-line bg-surface px-2 py-1.5 text-sm";
  return (
    <form method="get" className="flex flex-wrap items-end gap-3 rounded-lg border border-line bg-surface p-3 mb-6" aria-label={d.common.filters}>
      {keep.map((k) => v(k) && <input key={k} type="hidden" name={k} value={v(k)} />)}
      <label className="flex flex-col gap-1 text-xs text-muted">{d.common.from}
        <input type="date" name="date_from" defaultValue={v("date_from")} className={field} />
      </label>
      <label className="flex flex-col gap-1 text-xs text-muted">{d.common.to}
        <input type="date" name="date_to" defaultValue={v("date_to")} className={field} />
      </label>
      <label className="flex flex-col gap-1 text-xs text-muted">{d.common.language}
        <select name="language" defaultValue={v("language")} className={field}>
          <option value="">{d.common.all}</option>
          {LANGS.map((x) => <option key={x} value={x}>{x.toUpperCase()}</option>)}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-xs text-muted">{d.common.operatingBase}
        <select name="operating_base" defaultValue={v("operating_base")} className={field}>
          <option value="">{d.common.all}</option>
          {BASES.map((x) => <option key={x} value={x}>{(d.bases as Record<string, string>)[x]}</option>)}
        </select>
      </label>
      {showDemo && (
        <label className="flex flex-col gap-1 text-xs text-muted">{d.common.demo}
          <select name="demo" defaultValue={v("demo") || "include"} className={field}>
            <option value="include">{d.common.demoInclude}</option>
            <option value="exclude">{d.common.demoExclude}</option>
            <option value="only">{d.common.demoOnly}</option>
          </select>
        </label>
      )}
      <div className="flex gap-2">
        <button type="submit" className="rounded-md bg-accent text-accent-ink px-3 py-1.5 text-sm font-medium">{d.common.apply}</button>
        <a href="?" className="rounded-md border border-line px-3 py-1.5 text-sm">{d.common.reset}</a>
      </div>
    </form>
  );
}
