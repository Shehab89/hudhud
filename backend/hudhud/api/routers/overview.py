"""Headline indicators, timelines and the daily summary."""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, literal_column, select

from hudhud.api.deps import DB, F, Filters, apply_filters
from hudhud.db import models as m

router = APIRouter(tags=["overview"])


def _kpis(db: DB, f: Filters) -> dict:
    A = m.Article
    ids = apply_filters(select(A.id), f).subquery()
    row = db.execute(
        select(
            func.count(A.id),
            func.count(func.distinct(func.coalesce(A.story_cluster_id, -A.id))),
            func.count(func.distinct(A.source_id)),
            func.count(func.distinct(A.language)),
            func.count(A.id).filter(A.is_demo.is_(True)),
        ).where(A.id.in_(select(ids.c.id)))
    ).one()
    events = (
        db.scalar(
            select(func.count(func.distinct(m.EventMention.event_id))).where(
                m.EventMention.article_id.in_(select(ids.c.id))
            )
        )
        or 0
    )
    actors = (
        db.scalar(
            select(func.count(func.distinct(m.EntityMention.entity_id)))
            .join(m.Entity, m.Entity.id == m.EntityMention.entity_id)
            .where(m.EntityMention.article_id.in_(select(ids.c.id)), m.Entity.entity_type != "location")
        )
        or 0
    )
    return {
        "articles": row[0],
        "unique_stories": row[1],
        "sources_active": row[2],
        "languages": row[3],
        "demo_articles": row[4],
        "events": events,
        "actors_mentioned": actors,
    }


@router.get("/overview", summary="Headline indicators for the selected period, with the previous period")
def overview(db: DB, f: F) -> dict:
    days = (f.date_to - f.date_from).days + 1
    prev = Filters(
        **{
            **f.__dict__,
            "date_from": f.date_from - dt.timedelta(days=days),
            "date_to": f.date_from - dt.timedelta(days=1),
        }
    )
    cur, before = _kpis(db, f), _kpis(db, prev)
    summary = {
        s.language: {"day": s.day, "content": s.content, "method": s.method}
        for s in db.scalars(
            select(m.DailySummary).where(
                m.DailySummary.day == select(func.max(m.DailySummary.day)).scalar_subquery()
            )
        )
    }
    last_run = db.scalar(select(m.PipelineRun).order_by(m.PipelineRun.started_at.desc()).limit(1))
    return {
        "filters": f.as_dict(),
        "current": cur,
        "previous": before,
        "contains_demo": cur["demo_articles"] > 0,
        "summary": summary,
        "last_pipeline_run": {
            "id": last_run.id,
            "status": last_run.status,
            "started_at": last_run.started_at,
            "finished_at": last_run.finished_at,
        }
        if last_run
        else None,
    }


SPLITS = {"language", "operating_base", "source_group"}


@router.get("/timeline", summary="Daily article counts, optionally split by a dimension")
def timeline(
    db: DB,
    f: F,
    split: Annotated[
        Literal["none", "language", "operating_base", "source_group", "sentiment", "category"], Query()
    ] = "none",
) -> dict:
    A = m.Article
    day = func.date_trunc("day", A.published_at).label("day")
    stmt = apply_filters(select(day), f)
    if split == "none":
        key = literal_column("'articles'")
    elif split in SPLITS:
        stmt = stmt.join(m.Source, m.Source.id == A.source_id)
        key = {
            "language": func.coalesce(A.language, "unknown"),
            "operating_base": m.Source.operating_base,
            "source_group": m.Source.source_group,
        }[split]
    elif split == "sentiment":
        stmt = stmt.outerjoin(
            m.SentimentAnalysis,
            (m.SentimentAnalysis.article_id == A.id) & m.SentimentAnalysis.is_current.is_(True),
        )
        key = func.coalesce(m.SentimentAnalysis.polarity, "not_analysed")
    else:  # top-level category of the primary assignment
        C, P = m.Category, m.Category.__table__.alias("p")
        stmt = (
            stmt.outerjoin(
                m.CategoryAssignment,
                (m.CategoryAssignment.article_id == A.id)
                & m.CategoryAssignment.is_current.is_(True)
                & (m.CategoryAssignment.rank == "primary"),
            )
            .outerjoin(C, C.id == m.CategoryAssignment.category_id)
            .outerjoin(P, P.c.id == C.parent_id)
        )
        key = func.coalesce(P.c.slug, C.slug, "uncategorised")
    rows = db.execute(
        stmt.add_columns(key.label("k"), func.count(A.id)).group_by(day, key).order_by(day)
    ).all()
    series: dict[str, dict[str, int]] = {}
    for d, k, n in rows:
        series.setdefault(d.date().isoformat(), {})[str(k)] = n
    days = [
        (f.date_from + dt.timedelta(days=i)).isoformat() for i in range((f.date_to - f.date_from).days + 1)
    ]
    keys = sorted({k for v in series.values() for k in v})
    return {
        "split": split,
        "days": days,
        "keys": keys,
        "series": {k: [series.get(d, {}).get(k, 0) for d in days] for k in keys},
    }


@router.get("/summary/{day}", summary="Descriptive daily summary (template-generated, EN + AR)")
def daily_summary(db: DB, day: dt.date) -> dict:
    rows = list(db.scalars(select(m.DailySummary).where(m.DailySummary.day == day)))
    if not rows:
        raise HTTPException(404, "no summary for this day")
    return {
        "day": day,
        "summaries": {r.language: r.content for r in rows},
        "data": rows[0].data,
        "method": rows[0].method,
    }
