"""Summarise a live ingestion run: feed health, articles per source, and a sample of real articles.

Writes report.md and report.json into the directory given as the first argument.
Only non-demo rows are counted.
"""

import json
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
out.mkdir(parents=True, exist_ok=True)
eng = create_engine(os.environ["DATABASE_URL"])

with eng.connect() as c:
    feeds = (
        c.execute(
            text("""
        select s.slug, s.name, s.source_group, f.url, f.health_status, f.last_item_count, f.consecutive_failures
        from source_feeds f join sources s on s.id = f.source_id
        where not s.is_demo and f.active order by s.source_group, s.slug""")
        )
        .mappings()
        .all()
    )
    per_source = (
        c.execute(
            text("""
        select s.slug, s.name, s.source_group, count(a.id) n,
               array_agg(distinct a.language) filter (where a.language is not null) langs
        from sources s join articles a on a.source_id = s.id
        where not a.is_demo group by s.slug, s.name, s.source_group order by n desc""")
        )
        .mappings()
        .all()
    )
    langs = c.execute(
        text("""select coalesce(language,'?') l, count(*) n from articles
        where not is_demo group by 1 order by 2 desc""")
    ).all()
    sample = (
        c.execute(
            text("""
        select distinct on (s.slug) s.name source, a.title, a.url, a.language, a.published_at
        from articles a join sources s on s.id = a.source_id
        where not a.is_demo order by s.slug, a.published_at desc nulls last""")
        )
        .mappings()
        .all()
    )
    errors = c.execute(
        text("""select stage, error_type, count(*) n from pipeline_errors
        group by 1, 2 order by 3 desc limit 20""")
    ).all()
    total = c.execute(text("select count(*) from articles where not is_demo")).scalar()

health: dict[str, int] = {}
for f in feeds:
    health[f["health_status"]] = health.get(f["health_status"], 0) + 1

data = {
    "articles": total,
    "sources_with_articles": len(per_source),
    "feeds": len(feeds),
    "feed_health": health,
    "languages": {lang: n for lang, n in langs},
    "per_source": [dict(r) for r in per_source],
    "feeds_detail": [dict(r) for r in feeds],
    "sample": [{**dict(r), "published_at": str(r["published_at"])} for r in sample],
    "errors": [{"stage": s, "type": t, "n": n} for s, t, n in errors],
}
(out / "report.json").write_text(json.dumps(data, ensure_ascii=False, indent=1, default=str))

md = [
    "# Live ingestion report\n",
    f"Real (non-demo) articles: **{total}** from **{len(per_source)}** outlets.",
    f"Active feeds: {len(feeds)}; health: {health}.",
    f"Languages: {dict(langs)}.\n",
    "## Articles per outlet\n",
    "| Outlet | Group | Articles | Languages |",
    "|---|---|---|---|",
]
md += [
    f"| {r['name']} | {r['source_group']} | {r['n']} | {', '.join(r['langs'] or [])} |" for r in per_source
]
md += ["\n## One recent article per outlet\n", "| Outlet | Lang | Title |", "|---|---|---|"]
md += [
    f"| {r['source']} | {r['language']} | [{(r['title'] or '').replace('|', '/')[:120]}]({r['url']}) |"
    for r in sample
]
md += ["\n## Failing feeds\n", "| Outlet | Feed | Status |", "|---|---|---|"]
md += [
    f"| {f['name']} | {f['url']} | {f['health_status']} |"
    for f in feeds
    if f["health_status"] not in ("healthy", "ok")
]
md += ["\n## Pipeline errors\n"] + [f"- {s} / {t}: {n}" for s, t, n in errors]
(out / "report.md").write_text("\n".join(md) + "\n")
print("\n".join(md[:5]))
