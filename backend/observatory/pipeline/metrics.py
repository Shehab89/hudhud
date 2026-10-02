"""Stage 5: daily aggregates (idempotent per day), drift checks and the daily summary.

Aggregates are recomputed for the affected days with delete+insert, so re-running a
day never double counts. Exact duplicates are excluded from all counts; syndicated
copies are counted as articles but the "unique_stories" figure counts story clusters.
"""

from __future__ import annotations

import datetime as dt
import math
from collections import Counter

import structlog
from sqlalchemy import delete, text
from sqlalchemy.orm import Session

from observatory.db import models as m

log = structlog.get_logger()


def shannon(counts: list[int]) -> float | None:
    total = sum(counts)
    if total == 0:
        return None
    return round(-sum((c / total) * math.log(c / total) for c in counts if c), 4)


def js_divergence(p: dict[str, float], q: dict[str, float]) -> float:
    keys = set(p) | set(q)
    sp, sq = sum(p.values()) or 1.0, sum(q.values()) or 1.0
    P = {k: p.get(k, 0) / sp for k in keys}
    Q = {k: q.get(k, 0) / sq for k in keys}
    M = {k: 0.5 * (P[k] + Q[k]) for k in keys}

    def kl(a, b):
        return sum(a[k] * math.log(a[k] / b[k]) for k in keys if a[k] > 0 and b[k] > 0)

    return round(0.5 * kl(P, M) + 0.5 * kl(Q, M), 4)


BASE = "a.deleted_at IS NULL AND a.duplicate_of_id IS NULL AND a.published_at >= :d AND a.published_at < :d1"


def compute_day(session: Session, day: dt.date) -> None:
    p = {
        "d": dt.datetime.combine(day, dt.time.min, tzinfo=dt.UTC),
        "d1": dt.datetime.combine(day + dt.timedelta(days=1), dt.time.min, tzinfo=dt.UTC),
    }
    q = lambda sql: session.execute(text(sql), p).all()  # noqa: E731

    langs = dict(q(f"SELECT coalesce(language,'unknown'), count(*) FROM articles a WHERE {BASE} GROUP BY 1"))
    groups = dict(
        q(
            f"SELECT s.source_group, count(*) FROM articles a JOIN sources s ON s.id=a.source_id WHERE {BASE} GROUP BY 1"
        )
    )
    sources = dict(q(f"SELECT a.source_id, count(*) FROM articles a WHERE {BASE} GROUP BY 1"))
    total_all = session.execute(
        text(
            "SELECT count(*) FROM articles a WHERE a.deleted_at IS NULL AND a.published_at >= :d AND a.published_at < :d1"
        ),
        p,
    ).scalar()
    stories = session.execute(
        text(f"SELECT count(DISTINCT coalesce(a.story_cluster_id, -a.id)) FROM articles a WHERE {BASE}"), p
    ).scalar()
    sentiments = dict(
        q(f"""SELECT sa.polarity, count(*) FROM sentiment_analysis sa JOIN articles a ON a.id=sa.article_id
                            WHERE sa.is_current AND {BASE} GROUP BY 1""")
    )
    cat_counts = [
        r[1]
        for r in q(f"""SELECT ca.category_id, count(*) FROM category_assignments ca JOIN articles a ON a.id=ca.article_id
                            WHERE ca.is_current AND ca.rank='primary' AND {BASE} GROUP BY 1""")
    ]
    n = sum(langs.values())
    session.execute(delete(m.DailyMetric).where(m.DailyMetric.day == day))
    session.add(
        m.DailyMetric(
            day=day,
            articles=n,
            unique_stories=stories or 0,
            sources_active=len(sources),
            duplicate_rate=round(1 - n / total_all, 4) if total_all else None,
            language_distribution=langs,
            group_distribution=groups,
            sentiment_distribution=sentiments,
            topic_entropy=shannon(cat_counts),
            source_diversity=shannon(list(sources.values())),
            language_diversity=shannon(list(langs.values())),
        )
    )

    # categories (rolled up to their parent too) and topics
    session.execute(delete(m.CategoryMetric).where(m.CategoryMetric.day == day))
    sent_expr = (
        "avg(CASE sa.polarity WHEN 'positive' THEN 1 WHEN 'negative' THEN -1 WHEN 'neutral' THEN 0 END)"
    )
    for dim, sql in (
        (
            "category",
            f"""SELECT x.cid, count(DISTINCT a.id), count(DISTINCT coalesce(a.story_cluster_id,-a.id)),
                count(DISTINCT a.source_id), count(DISTINCT a.language), {sent_expr}
                FROM (SELECT ca.article_id, ca.category_id cid FROM category_assignments ca WHERE ca.is_current
                      UNION SELECT ca.article_id, c.parent_id FROM category_assignments ca JOIN categories c ON c.id=ca.category_id
                      WHERE ca.is_current AND c.parent_id IS NOT NULL) x
                JOIN articles a ON a.id=x.article_id
                LEFT JOIN sentiment_analysis sa ON sa.article_id=a.id AND sa.is_current
                WHERE {BASE} GROUP BY 1""",
        ),
        (
            "topic",
            f"""SELECT ta.topic_id, count(DISTINCT a.id), count(DISTINCT coalesce(a.story_cluster_id,-a.id)),
                count(DISTINCT a.source_id), count(DISTINCT a.language), {sent_expr}
                FROM topic_assignments ta JOIN topic_models tm ON tm.id=ta.topic_model_id AND tm.status='active'
                JOIN articles a ON a.id=ta.article_id
                LEFT JOIN sentiment_analysis sa ON sa.article_id=a.id AND sa.is_current
                WHERE {BASE} GROUP BY 1""",
        ),
    ):
        for ref, cnt, st, sc, lc, ms in q(sql):
            if ref is None:
                continue
            session.add(
                m.CategoryMetric(
                    dimension=dim,
                    ref_id=ref,
                    day=day,
                    article_count=cnt,
                    story_count=st,
                    source_count=sc,
                    language_count=lc,
                    mean_sentiment=round(float(ms), 4) if ms is not None else None,
                )
            )

    session.execute(delete(m.SourceMetric).where(m.SourceMetric.day == day))
    cat_by_source: dict[int, Counter] = {}
    for (
        sid,
        slug,
        cnt,
    ) in q(f"""SELECT a.source_id, coalesce(pc.slug, c.slug), count(*) FROM category_assignments ca
            JOIN categories c ON c.id=ca.category_id LEFT JOIN categories pc ON pc.id=c.parent_id
            JOIN articles a ON a.id=ca.article_id WHERE ca.is_current AND ca.rank='primary' AND {BASE} GROUP BY 1,2"""):
        cat_by_source.setdefault(sid, Counter())[slug] = cnt
    for sid, cnt, ms in q(f"""SELECT a.source_id, count(DISTINCT a.id), {sent_expr} FROM articles a
            LEFT JOIN sentiment_analysis sa ON sa.article_id=a.id AND sa.is_current WHERE {BASE} GROUP BY 1"""):
        session.add(
            m.SourceMetric(
                source_id=sid,
                day=day,
                article_count=cnt,
                mean_sentiment=round(float(ms), 4) if ms is not None else None,
                category_distribution=dict(cat_by_source.get(sid, {})),
            )
        )

    session.execute(delete(m.EntityMetric).where(m.EntityMetric.day == day))
    for (
        eid,
        mc,
        ac,
        sc,
        ts,
    ) in q(f"""SELECT em.entity_id, count(*), count(DISTINCT a.id), count(DISTINCT a.source_id),
            (SELECT avg(t.score) FROM targeted_sentiment t JOIN articles a2 ON a2.id=t.article_id
             WHERE t.entity_id=em.entity_id AND t.is_current AND a2.published_at >= :d AND a2.published_at < :d1)
            FROM entity_mentions em JOIN articles a ON a.id=em.article_id
            WHERE em.entity_id IS NOT NULL AND {BASE} GROUP BY 1"""):
        session.add(
            m.EntityMetric(
                entity_id=eid,
                day=day,
                mention_count=mc,
                article_count=ac,
                source_count=sc,
                mean_targeted_sentiment=round(float(ts), 4) if ts is not None else None,
            )
        )

    session.execute(delete(m.TerminologyVariant).where(m.TerminologyVariant.day == day))
    for (
        alias_id,
        sid,
        eid,
        cnt,
    ) in q(f"""SELECT em.alias_id, a.source_id, em.entity_id, count(*) FROM entity_mentions em
            JOIN articles a ON a.id=em.article_id WHERE em.alias_id IS NOT NULL AND {BASE} GROUP BY 1,2,3"""):
        session.add(
            m.TerminologyVariant(alias_id=alias_id, source_id=sid, day=day, entity_id=eid, frequency=cnt)
        )
    session.flush()


def days_to_compute(session: Session, today: dt.date, window: int = 14) -> list[dt.date]:
    """The trend windows (7 + 7 days) plus any older day whose articles changed recently."""
    touched = session.scalars(
        text("""SELECT DISTINCT (published_at AT TIME ZONE 'UTC')::date FROM articles
        WHERE updated_at >= now() - interval '36 hours' AND published_at IS NOT NULL""")
    ).all()
    days = {today - dt.timedelta(days=i) for i in range(window)} | {d for d in touched if d <= today}
    return sorted(days)


def run_metrics(session: Session, run_id: int | None = None) -> dict:
    today = dt.datetime.now(dt.UTC).date()
    computed = []
    for day in days_to_compute(session, today):
        compute_day(session, day)
        computed.append(day.isoformat())
    session.commit()
    flags = run_drift(session, today, run_id)
    session.commit()
    from observatory.analytics.summary import build_daily_summary

    build_daily_summary(session, today)
    session.commit()
    log.info("metrics_done", days=len(computed), drift_flags=flags)
    return {
        "days_computed": len(computed),
        "first_day": computed[0],
        "last_day": computed[-1],
        "drift_flags": flags,
    }


def run_drift(session: Session, day: dt.date, run_id: int | None) -> int:
    """Compare the last 7 days with the 7 before on language, source-group and vocabulary."""
    p = {
        "a": day - dt.timedelta(days=6),
        "b": day,
        "c": day - dt.timedelta(days=13),
        "e": day - dt.timedelta(days=7),
    }

    def dist(col: str, a: str, b: str) -> dict[str, float]:
        rows = session.execute(
            text(f"SELECT {col} FROM daily_metrics WHERE day BETWEEN :{a} AND :{b}"), p
        ).all()
        out: Counter = Counter()
        for (d,) in rows:
            out.update(d or {})
        return dict(out)

    checks = {
        "language_distribution_jsd": (
            dist("language_distribution", "a", "b"),
            dist("language_distribution", "c", "e"),
            0.10,
        ),
        "source_group_distribution_jsd": (
            dist("group_distribution", "a", "b"),
            dist("group_distribution", "c", "e"),
            0.15,
        ),
        "sentiment_distribution_jsd": (
            dist("sentiment_distribution", "a", "b"),
            dist("sentiment_distribution", "c", "e"),
            0.10,
        ),
    }
    vocab_recent = dict(
        session.execute(
            text("""
        SELECT w, count(*) FROM (SELECT unnest(string_to_array(title_normalized, ' ')) w FROM articles
        WHERE published_at::date BETWEEN :a AND :b AND duplicate_of_id IS NULL) t WHERE length(w) > 3 GROUP BY 1
        ORDER BY 2 DESC LIMIT 500"""),
            p,
        ).all()
    )
    vocab_prev = dict(
        session.execute(
            text("""
        SELECT w, count(*) FROM (SELECT unnest(string_to_array(title_normalized, ' ')) w FROM articles
        WHERE published_at::date BETWEEN :c AND :e AND duplicate_of_id IS NULL) t WHERE length(w) > 3 GROUP BY 1
        ORDER BY 2 DESC LIMIT 500"""),
            p,
        ).all()
    )
    checks["vocabulary_jsd_top500"] = (vocab_recent, vocab_prev, 0.35)
    flagged = 0
    session.execute(delete(m.DriftReport).where(m.DriftReport.day == day))
    for metric, (cur, prev, thr) in checks.items():
        if not cur or not prev:
            continue
        v = js_divergence(cur, prev)
        flagged += v > thr
        session.add(
            m.DriftReport(
                run_id=run_id,
                day=day,
                metric=metric,
                value=v,
                threshold=thr,
                flagged=v > thr,
                details={"recent_n": sum(cur.values()), "previous_n": sum(prev.values())},
            )
        )
    return int(flagged)
