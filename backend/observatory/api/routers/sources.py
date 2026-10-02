"""Source registry, evidence-backed orientation profiles and source comparison."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from observatory.api.deps import DB, F, Filters, apply_filters
from observatory.api.util import article_summaries
from observatory.db import models as m

router = APIRouter(tags=["sources"])

ORIENTATION_NOTE = (
    "Orientation describes ownership, funding and stated editorial alignment, documented with "
    "evidence. It is not a measure of accuracy, quality or reliability, and it is separate from "
    "the sentiment, framing and topic of any individual article."
)


def _orientation(o: m.SourceOrientation | None) -> dict | None:
    if o is None:
        return None
    return {
        "simplified": o.simplified,
        "dimensions": o.dimensions,
        "confidence": o.confidence,
        "evidence": o.evidence,
        "method": o.method,
        "valid_from": o.valid_from,
        "valid_to": o.valid_to,
        "last_reviewed": o.last_reviewed,
        "review_status": o.review_status,
        "evidence_items": [
            {"url": e.url, "type": e.evidence_type, "note": e.note, "accessed_at": e.accessed_at}
            for e in o.evidence_items
        ],
    }


@router.get("/sources", summary="Source registry with orientation, health and article counts")
def list_sources(
    db: DB,
    f: F,
    group: Annotated[str | None, Query()] = None,
    operating_base: Annotated[str | None, Query()] = None,
    country: Annotated[str | None, Query(min_length=2, max_length=2)] = None,
    active_only: bool = False,
) -> dict:
    q = (
        select(m.Source)
        .where(m.Source.deleted_at.is_(None))
        .options(
            selectinload(m.Source.orientations).selectinload(m.SourceOrientation.evidence_items),
            selectinload(m.Source.languages),
            selectinload(m.Source.feeds),
        )
    )
    if group:
        q = q.where(m.Source.source_group == group)
    if operating_base:
        q = q.where(m.Source.operating_base == operating_base)
    if country:
        q = q.where(m.Source.country == country.upper())
    if active_only:
        q = q.where(m.Source.active.is_(True))
    if f.demo == "exclude":
        q = q.where(m.Source.is_demo.is_(False))
    elif f.demo == "only":
        q = q.where(m.Source.is_demo.is_(True))
    counts = dict(
        db.execute(
            apply_filters(select(m.Article.source_id, func.count()), f).group_by(m.Article.source_id)
        ).all()
    )
    out = []
    for s in db.scalars(q.order_by(m.Source.source_group, m.Source.name)):
        cur = next((o for o in s.orientations if o.valid_to is None), None)
        out.append(
            {
                "slug": s.slug,
                "name": s.name,
                "name_native": s.name_native,
                "url": s.url,
                "country": s.country,
                "source_type": s.source_type,
                "source_group": s.source_group,
                "operating_base": s.operating_base,
                "languages": [lang.language_code for lang in s.languages],
                "active": s.active,
                "is_demo": s.is_demo,
                "access_policy": s.access_policy,
                "health_status": s.health_status,
                "last_success_at": s.last_success_at,
                "feeds": len(s.feeds),
                "orientation": {
                    "simplified": cur.simplified,
                    "confidence": cur.confidence,
                    "method": cur.method,
                }
                if cur
                else None,
                "articles": counts.get(s.id, 0),
            }
        )
    return {"note": ORIENTATION_NOTE, "count": len(out), "sources": out}


def _profile_stats(db: DB, f: Filters, source_id: int) -> dict:
    ids = apply_filters(select(m.Article.id), f).where(m.Article.source_id == source_id).subquery()
    in_ids = select(ids.c.id)
    day = func.date_trunc("day", m.Article.published_at)
    series = db.execute(
        select(day, func.count()).where(m.Article.id.in_(in_ids)).group_by(day).order_by(day)
    ).all()
    C, P = m.Category, m.Category.__table__.alias("p")
    cats = db.execute(
        select(func.coalesce(P.c.slug, C.slug), func.count())
        .select_from(m.CategoryAssignment)
        .join(C, C.id == m.CategoryAssignment.category_id)
        .outerjoin(P, P.c.id == C.parent_id)
        .where(
            m.CategoryAssignment.is_current.is_(True),
            m.CategoryAssignment.rank == "primary",
            m.CategoryAssignment.article_id.in_(in_ids),
        )
        .group_by(func.coalesce(P.c.slug, C.slug))
        .order_by(func.count().desc())
    ).all()
    sentiment = dict(
        db.execute(
            select(m.SentimentAnalysis.polarity, func.count())
            .where(m.SentimentAnalysis.is_current.is_(True), m.SentimentAnalysis.article_id.in_(in_ids))
            .group_by(m.SentimentAnalysis.polarity)
        ).all()
    )
    tone = db.execute(
        select(m.EmotionAnalysis.dominant, func.count())
        .where(
            m.EmotionAnalysis.is_current.is_(True),
            m.EmotionAnalysis.kind == "tone",
            m.EmotionAnalysis.article_id.in_(in_ids),
        )
        .group_by(m.EmotionAnalysis.dominant)
        .order_by(func.count().desc())
    ).all()
    frames = db.execute(
        select(m.Frame.slug, m.Frame.name_en, m.Frame.name_ar, func.count())
        .join(m.FramingAnalysis, m.FramingAnalysis.frame_id == m.Frame.id)
        .where(m.FramingAnalysis.is_current.is_(True), m.FramingAnalysis.article_id.in_(in_ids))
        .group_by(m.Frame.id)
        .order_by(func.count().desc())
    ).all()
    terms = db.execute(
        select(
            m.Entity.slug,
            m.Entity.name_en,
            m.EntityAlias.surface_form,
            m.EntityAlias.alias_type,
            m.EntityAlias.framing_note,
            func.count(),
        )
        .select_from(m.EntityMention)
        .join(m.EntityAlias, m.EntityAlias.id == m.EntityMention.alias_id)
        .join(m.Entity, m.Entity.id == m.EntityMention.entity_id)
        .where(
            m.EntityMention.article_id.in_(in_ids),
            m.Entity.entity_type != "location",
            m.Entity.entity_type != "country",
        )
        .group_by(m.Entity.id, m.EntityAlias.id)
        .order_by(func.count().desc())
        .limit(40)
    ).all()
    actors = db.execute(
        select(
            m.Entity.slug,
            m.Entity.name_en,
            m.Entity.name_ar,
            func.count(func.distinct(m.EntityMention.article_id)),
            func.avg(m.TargetedSentiment.score),
        )
        .join(m.EntityMention, m.EntityMention.entity_id == m.Entity.id)
        .outerjoin(
            m.TargetedSentiment,
            (m.TargetedSentiment.entity_id == m.Entity.id)
            & (m.TargetedSentiment.article_id == m.EntityMention.article_id)
            & m.TargetedSentiment.is_current.is_(True),
        )
        .where(m.EntityMention.article_id.in_(in_ids), m.Entity.entity_type != "location")
        .group_by(m.Entity.id)
        .order_by(func.count(func.distinct(m.EntityMention.article_id)).desc())
        .limit(15)
    ).all()
    total = db.scalar(select(func.count()).select_from(ids)) or 0
    return {
        "articles": total,
        "series": [{"day": d.date(), "articles": n} for d, n in series],
        "categories": [{"slug": s, "articles": n} for s, n in cats],
        "sentiment": sentiment,
        "tone": [{"tone": t, "articles": n} for t, n in tone],
        "frames": [{"slug": r[0], "name_en": r[1], "name_ar": r[2], "articles": r[3]} for r in frames],
        "terminology": [
            {
                "entity": r[0],
                "entity_name": r[1],
                "term": r[2],
                "alias_type": r[3],
                "framing_note": r[4],
                "mentions": r[5],
            }
            for r in terms
        ],
        "actors": [
            {
                "slug": r[0],
                "name_en": r[1],
                "name_ar": r[2],
                "articles": r[3],
                "mean_targeted_sentiment": round(float(r[4]), 3) if r[4] is not None else None,
            }
            for r in actors
        ],
    }


@router.get(
    "/sources/{slug}", summary="Source profile: registry entry, orientation history, coverage patterns"
)
def get_source(db: DB, f: F, slug: str) -> dict:
    s = db.scalar(
        select(m.Source)
        .where(m.Source.slug == slug)
        .options(
            selectinload(m.Source.orientations).selectinload(m.SourceOrientation.evidence_items),
            selectinload(m.Source.languages),
            selectinload(m.Source.feeds),
        )
    )
    if s is None:
        raise HTTPException(404, "source not found")
    history = sorted(s.orientations, key=lambda o: (o.valid_from is None, o.valid_from), reverse=True)
    recent = article_summaries(
        db,
        db.scalars(
            apply_filters(select(m.Article), f)
            .where(m.Article.source_id == s.id)
            .order_by(m.Article.published_at.desc())
            .limit(15)
        ),
    )
    return {
        "note": ORIENTATION_NOTE,
        "slug": s.slug,
        "name": s.name,
        "name_native": s.name_native,
        "url": s.url,
        "domain": s.domain,
        "country": s.country,
        "source_type": s.source_type,
        "source_group": s.source_group,
        "operating_base": s.operating_base,
        "geographic_focus": s.geographic_focus,
        "yemen_coverage": s.yemen_coverage,
        "languages": [lang.language_code for lang in s.languages],
        "ownership": s.ownership_description,
        "ownership_evidence_urls": s.ownership_evidence_urls,
        "access_policy": s.access_policy,
        "active": s.active,
        "is_demo": s.is_demo,
        "notes": s.notes,
        "health": {
            "status": s.health_status,
            "last_success_at": s.last_success_at,
            "last_failure_at": s.last_failure_at,
            "consecutive_failures": s.consecutive_failures,
        },
        "feeds": [
            {
                "url": fd.url,
                "type": fd.feed_type,
                "verified": fd.verified,
                "verified_at": fd.verified_at,
                "active": fd.active,
                "health_status": fd.health_status,
                "last_success_at": fd.last_success_at,
                "last_item_count": fd.last_item_count,
                "notes": fd.notes,
            }
            for fd in s.feeds
        ],
        "orientation": _orientation(next((o for o in s.orientations if o.valid_to is None), None)),
        "orientation_history": [_orientation(o) for o in history],
        "stats": _profile_stats(db, f, s.id),
        "recent_articles": recent,
    }


@router.get("/compare/sources", summary="Side-by-side comparison of 2-6 sources under the same filters")
def compare_sources(
    db: DB, f: F, slugs: Annotated[str, Query(description="Comma-separated source slugs (2-6).")]
) -> dict:
    wanted = [x.strip() for x in slugs.split(",") if x.strip()]
    if not 2 <= len(wanted) <= 6:
        raise HTTPException(422, "provide between 2 and 6 source slugs")
    out = []
    for slug in wanted:
        s = db.scalar(
            select(m.Source).where(m.Source.slug == slug).options(selectinload(m.Source.orientations))
        )
        if s is None:
            raise HTTPException(404, f"source not found: {slug}")
        cur = next((o for o in s.orientations if o.valid_to is None), None)
        out.append(
            {
                "slug": s.slug,
                "name": s.name,
                "operating_base": s.operating_base,
                "source_group": s.source_group,
                "is_demo": s.is_demo,
                "orientation": {"simplified": cur.simplified, "confidence": cur.confidence} if cur else None,
                **_profile_stats(db, f, s.id),
            }
        )
    shared = db.execute(
        select(m.Article.story_cluster_id, func.count(func.distinct(m.Source.slug)))
        .join(m.Source, m.Source.id == m.Article.source_id)
        .where(
            m.Source.slug.in_(wanted),
            m.Article.story_cluster_id.is_not(None),
            m.Article.published_at >= f.start,
            m.Article.published_at < f.end,
        )
        .group_by(m.Article.story_cluster_id)
        .having(func.count(func.distinct(m.Source.slug)) == len(wanted))
    ).all()
    return {
        "filters": f.as_dict(),
        "note": ORIENTATION_NOTE,
        "sources": out,
        "stories_covered_by_all": len(shared),
    }
