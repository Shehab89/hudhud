"use client";

import { useState } from "react";

type T = { token: string; load: string; errors: string; annotations: string; accept: string; reject: string };
type Row = Record<string, unknown>;

/** The token stays in this tab's memory only; it is never stored or bundled. */
export default function AdminConsole({ apiUrl, t }: { apiUrl: string; t: T }) {
  const [token, setToken] = useState("");
  const [runs, setRuns] = useState<Row[]>([]);
  const [errors, setErrors] = useState<Row[]>([]);
  const [anns, setAnns] = useState<Row[]>([]);
  const [msg, setMsg] = useState("");
  const call = async (path: string, init?: RequestInit) => {
    const r = await fetch(`${apiUrl}/api/v1/admin${path}`, { ...init, headers: { "X-Admin-Token": token, "Content-Type": "application/json" } });
    if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
    return r.json();
  };
  const load = async () => {
    setMsg("");
    try {
      const [a, b, c] = await Promise.all([call("/runs?limit=20"), call("/errors?limit=50"), call("/annotations")]);
      setRuns(a); setErrors(b); setAnns(c);
    } catch (e) { setMsg(String(e)); }
  };
  const review = async (id: unknown, status: string) => {
    try { await call(`/annotations/${id}`, { method: "PATCH", body: JSON.stringify({ status }) }); await load(); } catch (e) { setMsg(String(e)); }
  };
  return (
    <div className="flex flex-col gap-6">
      <form onSubmit={(e) => { e.preventDefault(); load(); }} className="flex gap-2 max-w-md">
        <input type="password" autoComplete="off" value={token} onChange={(e) => setToken(e.target.value)} aria-label={t.token} placeholder={t.token}
          className="flex-1 rounded-md border border-line bg-surface px-3 py-2" />
        <button className="rounded-md bg-accent text-accent-ink px-4 py-2 text-sm">{t.load}</button>
      </form>
      {msg && <p role="alert" className="text-sm text-accent break-all">{msg}</p>}
      <section><h2 className="font-semibold mb-2">Runs</h2>
        <div className="overflow-x-auto rounded-lg border border-line bg-surface"><table className="w-full text-xs"><tbody>
          {runs.map((r) => <tr key={String(r.id)} className="border-b border-line align-top"><td className="p-2">{String(r.id)}</td><td className="p-2">{String(r.started_at)}</td><td className="p-2">{String(r.status)}</td><td className="p-2">{String(r.errors)}</td><td className="p-2 font-mono whitespace-pre-wrap break-all max-w-xl">{JSON.stringify(r.stats).slice(0, 400)}</td></tr>)}
        </tbody></table></div></section>
      <section><h2 className="font-semibold mb-2">{t.errors}</h2>
        <ul className="text-xs flex flex-col gap-1 font-mono">{errors.map((e) => <li key={String(e.id)} className="break-all">[{String(e.stage)}] {String(e.source ?? "")} {String(e.error_type)}: {String(e.message).slice(0, 200)}</li>)}</ul></section>
      <section><h2 className="font-semibold mb-2">{t.annotations}</h2>
        <ul className="text-sm flex flex-col gap-2">{anns.map((a) => (
          <li key={String(a.id)} className="rounded border border-line p-2 flex flex-wrap gap-2 items-center">
            <span className="font-mono text-xs">#{String(a.id)} {String(a.target_type)} article {String(a.article_id)}: {JSON.stringify(a.corrected_value)}</span>
            <span className="text-muted">{String(a.note ?? "")}</span>
            <button className="ms-auto rounded border border-line px-2" onClick={() => review(a.id, "accepted")}>{t.accept}</button>
            <button className="rounded border border-line px-2" onClick={() => review(a.id, "rejected")}>{t.reject}</button>
          </li>))}</ul></section>
    </div>
  );
}
