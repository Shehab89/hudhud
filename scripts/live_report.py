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
        select s.slug, s.name, s.category, s.source_group, f.url, f.feed_type, f.health_status,
               f.last_item_count, f.consecutive_failures,
               (select e.error_type || ': ' || left(e.message, 160) from pipeline_errors e
                 where e.feed_id = f.id order by e.id desc limit 1) last_error
        from source_feeds f join sources s on s.id = f.source_id
        where not s.is_demo and f.active order by s.category, s.slug""")
        )
        .mappings()
        .all()
    )
    per_category = (
        c.execute(
            text("""
        select s.category, count(distinct s.id) sources,
               count(distinct s.id) filter (where s.active) collected,
               count(a.id) filter (where not a.is_demo) articles
        from sources s left join articles a on a.source_id = s.id
        where not s.is_demo and s.registry_status = 'curated' group by 1 order by 1""")
        )
        .mappings()
        .all()
    )
    per_source = (
        c.execute(
            text("""
        select s.slug, s.name, s.category, s.content_type, s.source_group, count(a.id) n,
               array_agg(distinct a.language) filter (where a.language is not null) langs
        from sources s join articles a on a.source_id = s.id
        where not a.is_demo group by s.slug, s.name, s.category, s.content_type, s.source_group
        order by n desc""")
        )
        .mappings()
        .all()
    )
    langs = c.execute(
        text("""select coalesce(language,'?') l, count(*) n from articles
        where not is_demo group by 1 order by 2 desc""")
    ).all()
    # Stories reported by more than one source, and by sources of more than one Yemeni camp:
    # what the comparison pages' "shared stories" are built from.
    shared = c.execute(
        text("""select count(*) filter (where n_sources > 1), count(*) filter (where n_camps > 1)
        from (select a.story_cluster_id, count(distinct a.source_id) n_sources,
                     count(distinct s.yemen_political_alignment) filter (
                       where s.yemen_political_alignment in ('plc_government', 'ansar_allah', 'stc')) n_camps
              from articles a join sources s on s.id = a.source_id
              where not a.is_demo and a.story_cluster_id is not null group by 1) x""")
    ).one()
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
    # The stories behind those counts, so the matching can be read and judged, not just counted.
    story_rows = (
        c.execute(
            text("""
        select a.story_cluster_id cid, s.name source, s.yemen_political_alignment camp, a.title, a.url
        from articles a join sources s on s.id = a.source_id
        where not a.is_demo and a.story_cluster_id in (
            select story_cluster_id from articles where not is_demo and story_cluster_id is not null
            group by 1 having count(distinct source_id) > 1)
        order by a.story_cluster_id, a.published_at""")
        )
        .mappings()
        .all()
    )
    status = dict(
        c.execute(
            text("select processing_status, count(*) from articles where not is_demo group by 1")
        ).all()
    )
    # what actually produced the stored results: method and model per analysis table
    produced = c.execute(
        text("""
        select t, a.method, coalesce(mo.name, '-') model, count(*) n from (
            select 'sentiment' t, method, model_version_id from sentiment_analysis where is_current
            union all select 'emotion/tone', method, model_version_id from emotion_analysis where is_current
            union all select 'frames', method, model_version_id from framing_analysis where is_current
            union all select 'categories', method, model_version_id from category_assignments where is_current
        ) a left join model_versions mv on mv.id = a.model_version_id
            left join models mo on mo.id = mv.model_id
        group by 1, 2, 3 order by 1, 4 desc""")
    ).all()
    last_analyse = c.execute(
        text("""select stats->'analyse'->'result' from pipeline_runs
        where stats ? 'analyse' order by id desc limit 1""")
    ).scalar()

health: dict[str, int] = {}
by_type: dict[str, dict[str, int]] = {}
for f in feeds:
    health[f["health_status"]] = health.get(f["health_status"], 0) + 1
    t = by_type.setdefault(f["feed_type"], {})
    t[f["health_status"]] = t.get(f["health_status"], 0) + 1

data = {
    "articles": total,
    "sources_with_articles": len(per_source),
    "feeds": len(feeds),
    "feed_health": health,
    "feed_health_by_type": by_type,
    "per_category": [dict(r) for r in per_category],
    "languages": {lang: n for lang, n in langs},
    "per_source": [dict(r) for r in per_source],
    "feeds_detail": [dict(r) for r in feeds],
    "sample": [{**dict(r), "published_at": str(r["published_at"])} for r in sample],
    "errors": [{"stage": s, "type": t, "n": n} for s, t, n in errors],
    "processing_status": status,
    "analysis_produced_by": [{"table": t, "method": mth, "model": mo, "n": n} for t, mth, mo, n in produced],
    "analyse_stage": last_analyse,
}
(out / "report.json").write_text(json.dumps(data, ensure_ascii=False, indent=1, default=str))

md = [
    "# Live ingestion report\n",
    f"Real (non-demo) articles: **{total}** from **{len(per_source)}** outlets, "
    f"published in the last {os.environ.get('LOOKBACK_DAYS', '3')} days.",
    f"Active feeds: {len(feeds)}; health: {health}.",
    f"Feed health by type: {by_type}.",
    f"Languages: {dict(langs)}.",
    f"NLP backend: {os.environ.get('NLP_BACKEND', 'auto')}. Stories reported by more than one source: "
    f"{shared[0]}; by more than one Yemeni camp (PLC, Ansar Allah, STC): {shared[1]}.\n",
    "## Curated sources by category\n",
    "| Category | Sources | Collected | Articles |",
    "|---|---|---|---|",
]
md += [f"| {r['category']} | {r['sources']} | {r['collected']} | {r['articles']} |" for r in per_category]
md += ["\n## Articles per source\n", "| Source | Category | Articles | Languages |", "|---|---|---|---|"]
md += [f"| {r['name']} | {r['category']} | {r['n']} | {', '.join(r['langs'] or [])} |" for r in per_source]
md += ["\n## One recent article per outlet\n", "| Outlet | Lang | Title |", "|---|---|---|"]
md += [
    f"| {r['source']} | {r['language']} | [{(r['title'] or '').replace('|', '/')[:120]}]({r['url']}) |"
    for r in sample
]
md += ["\n## Analysis\n", f"Articles by processing status: {status}."]
if last_analyse:
    md.append(
        f"Analyse stage: analysed {last_analyse.get('analysed')}, deferred to the next run "
        f"{last_analyse.get('deferred')}, embedder {last_analyse.get('embedder')}, transformer models "
        f"{last_analyse.get('transformer_models')}; seconds by part {last_analyse.get('seconds_by_part')}."
    )
md += ["", "| Result | Method | Model | Rows |", "|---|---|---|---:|"]
md += [f"| {t} | {mth} | {mo} | {n} |" for t, mth, mo, n in produced]

stories: dict[int, list[dict]] = {}
for r in story_rows:
    stories.setdefault(r["cid"], []).append(r)
CAMPS = {"plc_government", "ansar_allah", "stc"}
ranked = sorted(stories.values(), key=lambda rs: (-len({r["camp"] for r in rs} & CAMPS), -len(rs)))
md += [
    "\n## Stories reported by more than one source\n",
    "Grouped by the matching the comparison pages use (title similarity, plus embedding similarity when "
    "the models run). A group is a claim that these articles are about the same story; read them to judge it.",
    "Camp is the source's documented Yemeni affiliation, not a judgement of what it reported.\n",
]
for rs in ranked[:20]:
    camps = sorted({r["camp"] for r in rs} & CAMPS)
    md.append(f"**{len(rs)} articles, {len({r['source'] for r in rs})} sources; camps: {camps or 'none'}**\n")
    md += [
        f"- {r['source']} ({r['camp']}): [{(r['title'] or '').replace('|', '/')[:110]}]({r['url']})"
        for r in rs[:6]
    ]
    md.append("")
md += ["\n## Failing feeds\n", "| Source | Type | Feed | Status | Last error |", "|---|---|---|---|---|"]
md += [
    f"| {f['name']} | {f['feed_type']} | {f['url']} | {f['health_status']} | {(f['last_error'] or '').replace('|', '/')} |"
    for f in feeds
    if f["health_status"] not in ("healthy", "ok")
]
md += ["\n## Pipeline errors\n"] + [f"- {s} / {t}: {n}" for s, t, n in errors]
(out / "report.md").write_text("\n".join(md) + "\n")
print("\n".join(md[:5]))
