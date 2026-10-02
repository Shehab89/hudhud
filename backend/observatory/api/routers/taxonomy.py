"""Curated taxonomy: category tree, category profiles and trend statistics."""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from observatory.analytics.trends import compute_trends
from observatory.api.deps import DB, F, apply_filters
from observatory.api.schemas import TrendOut
from observatory.db import models as m

router = APIRouter(tags=["taxonomy"])


def _category_counts(db: DB, f) -> dict[int, int]:
    ids = apply_filters(select(m.Article.id), f).subquery()
    C = m.Category
    direct = dict(
        db.execute(
            select(
                m.CategoryAssignment.category_id, func.count(func.distinct(m.CategoryAssignment.article_id))
            )
            .where(
                m.CategoryAssignment.is_current.is_(True),
                m.CategoryAssignment.article_id.in_(select(ids.c.id)),
            )
            .group_by(m.CategoryAssignment.category_id)
        ).all()
    )
    rolled = dict(
        db.execute(
            select(C.parent_id, func.count(func.distinct(m.CategoryAssignment.article_id)))
            .join(C, C.id == m.CategoryAssignment.category_id)
            .where(
                m.CategoryAssignment.is_current.is_(True),
                C.parent_id.is_not(None),
                m.CategoryAssignment.article_id.in_(select(ids.c.id)),
            )
            .group_by(C.parent_id)
        ).all()
    )
    return {k: max(direct.get(k, 0), rolled.get(k, 0)) for k in set(direct) | set(rolled)}


@router.get("/categories", summary="Category tree with article counts for the selected filters")
def categories(db: DB, f: F) -> dict:
    counts = _category_counts(db, f)
    cats = list(db.scalars(select(m.Category).order_by(m.Category.level, m.Category.name_en)))
    children: dict[int, list] = {}
    for c in cats:
        if c.parent_id:
            children.setdefault(c.parent_id, []).append(
                {
                    "id": c.id,
                    "slug": c.slug,
                    "name_en": c.name_en,
                    "name_ar": c.name_ar,
                    "count": counts.get(c.id, 0),
                }
            )
    tree = [
        {
            "id": c.id,
            "slug": c.slug,
            "name_en": c.name_en,
            "name_ar": c.name_ar,
            "description": c.description,
            "count": counts.get(c.id, 0),
            "children": sorted(children.get(c.id, []), key=lambda x: -x["count"]),
        }
        for c in cats
        if c.parent_id is None
    ]
    return {"filters": f.as_dict(), "categories": sorted(tree, key=lambda x: -x["count"])}


@router.get("/categories/{slug}", summary="Category profile: volume, outlets, actors, sentiment and frames")
def category(db: DB, f: F, slug: str) -> dict:
    c = db.scalar(select(m.Category).where(m.Category.slug == slug))
    if c is None:
        raise HTTPException(404, "category not found")
    f.category = slug
    ids = apply_filters(select(m.Article.id), f).subquery()
    in_ids = m.Article.id.in_(select(ids.c.id))
    day = func.date_trunc("day", m.Article.published_at)
    series = db.execute(select(day, func.count()).where(in_ids).group_by(day).order_by(day)).all()
    by_source = db.execute(
        select(m.Source.slug, m.Source.name, m.Source.operating_base, func.count())
        .join(m.Article, m.Article.source_id == m.Source.id)
        .where(in_ids)
        .group_by(m.Source.id)
        .order_by(func.count().desc())
        .limit(15)
    ).all()
    by_base = dict(
        db.execute(
            select(m.Source.operating_base, func.count())
            .join(m.Article, m.Article.source_id == m.Source.id)
            .where(in_ids)
            .group_by(m.Source.operating_base)
        ).all()
    )
    actors = db.execute(
        select(
            m.Entity.slug,
            m.Entity.name_en,
            m.Entity.name_ar,
            func.count(func.distinct(m.EntityMention.article_id)),
        )
        .join(m.EntityMention, m.EntityMention.entity_id == m.Entity.id)
        .where(m.EntityMention.article_id.in_(select(ids.c.id)), m.Entity.entity_type != "location")
        .group_by(m.Entity.id)
        .order_by(func.count(func.distinct(m.EntityMention.article_id)).desc())
        .limit(12)
    ).all()
    sentiment = dict(
        db.execute(
            select(m.SentimentAnalysis.polarity, func.count())
            .where(
                m.SentimentAnalysis.is_current.is_(True), m.SentimentAnalysis.article_id.in_(select(ids.c.id))
            )
            .group_by(m.SentimentAnalysis.polarity)
        ).all()
    )
    frames = db.execute(
        select(m.Frame.slug, m.Frame.name_en, m.Frame.name_ar, func.count())
        .join(m.FramingAnalysis, m.FramingAnalysis.frame_id == m.Frame.id)
        .where(m.FramingAnalysis.is_current.is_(True), m.FramingAnalysis.article_id.in_(select(ids.c.id)))
        .group_by(m.Frame.id)
        .order_by(func.count().desc())
    ).all()
    subs = list(db.scalars(select(m.Category).where(m.Category.parent_id == c.id)))
    return {
        "id": c.id,
        "slug": c.slug,
        "name_en": c.name_en,
        "name_ar": c.name_ar,
        "description": c.description,
        "keywords": c.keywords,
        "parent_id": c.parent_id,
        "subcategories": [{"slug": s.slug, "name_en": s.name_en, "name_ar": s.name_ar} for s in subs],
        "series": [{"day": d.date(), "articles": n} for d, n in series],
        "top_sources": [
            {"slug": r[0], "name": r[1], "operating_base": r[2], "articles": r[3]} for r in by_source
        ],
        "by_operating_base": by_base,
        "top_actors": [{"slug": r[0], "name_en": r[1], "name_ar": r[2], "articles": r[3]} for r in actors],
        "sentiment": sentiment,
        "frames": [{"slug": r[0], "name_en": r[1], "name_ar": r[2], "articles": r[3]} for r in frames],
    }


@router.get(
    "/trends",
    response_model=list[TrendOut],
    summary="Emerging / declining / stable categories or topics (7-day windows)",
)
def trends(
    db: DB,
    dimension: Literal["category", "topic"] = "category",
    end: Annotated[dt.date | None, Query()] = None,
    window_days: Annotated[int, Query(ge=3, le=30)] = 7,
    level: Annotated[Literal["top", "all"], Query(description="Categories only.")] = "top",
    status: Literal["emerging", "declining", "stable"] | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> list[TrendOut]:
    end = end or dt.datetime.now(dt.UTC).date()
    if dimension == "category":
        q = select(m.Category)
        if level == "top":
            q = q.where(m.Category.parent_id.is_(None))
        refs = {c.id: (c.slug, c.name_en, c.name_ar) for c in db.scalars(q)}
    else:
        q = (
            select(m.Topic)
            .join(m.TopicModel, m.TopicModel.id == m.Topic.topic_model_id)
            .where(m.TopicModel.status == "active", m.TopicModel.scope == "global")
        )
        refs = {}
        for t in db.scalars(q):
            ar = db.scalar(
                select(m.TopicTranslation.label).where(
                    m.TopicTranslation.topic_id == t.id, m.TopicTranslation.language == "ar"
                )
            )
            refs[t.id] = (None, t.label, ar)
    out = []
    for t in compute_trends(db, dimension, end, window_days, list(refs)):
        if status and t.status != status:
            continue
        slug, label, label_ar = refs[t.ref_id]
        out.append(
            TrendOut(
                id=t.ref_id,
                slug=slug,
                label=label,
                label_ar=label_ar,
                frequency=t.frequency,
                previous=t.previous,
                growth_rate=t.growth_rate,
                acceleration=t.acceleration,
                source_count=t.source_count,
                source_diversity=t.source_diversity,
                language_count=t.language_count,
                status=t.status,
                series=t.series,
            )
        )
    return out[:limit]
