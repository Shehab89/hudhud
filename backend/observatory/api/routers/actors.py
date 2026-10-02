"""Actors: knowledge base, aliases/terminology, mentions and actor-targeted sentiment.

Only organisations, states and public figures in the curated knowledge base are profiled;
the platform never builds profiles of private individuals.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from observatory.api.deps import DB, F, Page, apply_filters
from observatory.api.util import article_summaries
from observatory.db import models as m

router = APIRouter(tags=["actors"])

TARGETED_NOTE = (
    "Actor-targeted sentiment is measured per sentence that names the actor, with the sentence "
    "kept as evidence. It describes the wording of coverage, not the actor's conduct, and it is "
    "not an approval rating."
)


@router.get("/actors", summary="Actors in the knowledge base with mention counts under the filters")
def list_actors(
    db: DB,
    f: F,
    page: Page,
    entity_type: Annotated[
        str | None, Query(description="political_actor, person, country, igo, ...")
    ] = None,
    include_locations: bool = False,
) -> dict:
    ids = apply_filters(select(m.Article.id), f).subquery()
    counts = (
        select(m.EntityMention.entity_id, func.count(func.distinct(m.EntityMention.article_id)).label("n"))
        .where(m.EntityMention.article_id.in_(select(ids.c.id)))
        .group_by(m.EntityMention.entity_id)
        .subquery()
    )
    q = (
        select(m.Entity, func.coalesce(counts.c.n, 0))
        .outerjoin(counts, counts.c.entity_id == m.Entity.id)
        .where(m.Entity.is_public_figure.is_(True))
    )
    if entity_type:
        q = q.where(m.Entity.entity_type == entity_type)
    elif not include_locations:
        q = q.where(m.Entity.entity_type != "location")
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    limit, offset = page
    rows = db.execute(
        q.order_by(func.coalesce(counts.c.n, 0).desc(), m.Entity.name_en).limit(limit).offset(offset)
    ).all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "slug": e.slug,
                "name_en": e.name_en,
                "name_ar": e.name_ar,
                "entity_type": e.entity_type,
                "subtype": e.subtype,
                "articles": n,
            }
            for e, n in rows
        ],
    }


@router.get("/actors/{slug}", summary="Actor profile: aliases, coverage, targeted sentiment with evidence")
def get_actor(db: DB, f: F, slug: str) -> dict:
    e = db.scalar(select(m.Entity).where(m.Entity.slug == slug))
    if e is None or not e.is_public_figure:
        raise HTTPException(404, "actor not found")
    ids = apply_filters(select(m.Article.id), f).subquery()
    in_ids = select(ids.c.id)
    mention_articles = select(m.EntityMention.article_id).where(
        m.EntityMention.entity_id == e.id, m.EntityMention.article_id.in_(in_ids)
    )
    day = func.date_trunc("day", m.Article.published_at)
    series = db.execute(
        select(day, func.count()).where(m.Article.id.in_(mention_articles)).group_by(day).order_by(day)
    ).all()
    T = m.TargetedSentiment
    by_base = db.execute(
        select(m.Source.operating_base, T.sentiment, func.count())
        .join(m.Article, m.Article.id == T.article_id)
        .join(m.Source, m.Source.id == m.Article.source_id)
        .where(T.entity_id == e.id, T.is_current.is_(True), T.article_id.in_(in_ids))
        .group_by(m.Source.operating_base, T.sentiment)
    ).all()
    base_dist: dict[str, dict[str, int]] = {}
    for base, sent, n in by_base:
        base_dist.setdefault(base, {})[sent] = n
    examples = db.execute(
        select(
            T.sentiment,
            T.score,
            T.evidence_sentence,
            T.confidence,
            T.method,
            m.Article.id,
            m.Article.title,
            m.Source.name,
            m.Source.operating_base,
            m.Article.is_demo,
        )
        .join(m.Article, m.Article.id == T.article_id)
        .join(m.Source, m.Source.id == m.Article.source_id)
        .where(T.entity_id == e.id, T.is_current.is_(True), T.article_id.in_(in_ids))
        .order_by(m.Article.published_at.desc())
        .limit(12)
    ).all()
    terms = db.execute(
        select(
            m.EntityAlias.surface_form,
            m.EntityAlias.language,
            m.EntityAlias.alias_type,
            m.EntityAlias.framing_note,
            m.Source.operating_base,
            func.count(),
        )
        .join(m.EntityMention, m.EntityMention.alias_id == m.EntityAlias.id)
        .join(m.Article, m.Article.id == m.EntityMention.article_id)
        .join(m.Source, m.Source.id == m.Article.source_id)
        .where(m.EntityMention.entity_id == e.id, m.EntityMention.article_id.in_(in_ids))
        .group_by(m.EntityAlias.id, m.Source.operating_base)
        .order_by(func.count().desc())
    ).all()
    co = db.execute(
        select(
            m.Entity.slug,
            m.Entity.name_en,
            m.Entity.name_ar,
            func.count(func.distinct(m.EntityMention.article_id)),
        )
        .join(m.EntityMention, m.EntityMention.entity_id == m.Entity.id)
        .where(
            m.EntityMention.article_id.in_(mention_articles),
            m.Entity.id != e.id,
            m.Entity.entity_type != "location",
        )
        .group_by(m.Entity.id)
        .order_by(func.count(func.distinct(m.EntityMention.article_id)).desc())
        .limit(12)
    ).all()
    recent = article_summaries(
        db,
        db.scalars(
            select(m.Article)
            .where(m.Article.id.in_(mention_articles))
            .order_by(m.Article.published_at.desc())
            .limit(15)
        ),
    )
    parent = db.get(m.Entity, e.parent_id) if e.parent_id else None
    return {
        "note": TARGETED_NOTE,
        "slug": e.slug,
        "name_en": e.name_en,
        "name_ar": e.name_ar,
        "entity_type": e.entity_type,
        "subtype": e.subtype,
        "description": e.description,
        "wikidata_id": e.wikidata_id,
        "parent": {"slug": parent.slug, "name_en": parent.name_en} if parent else None,
        "aliases": [
            {
                "surface_form": a.surface_form,
                "language": a.language,
                "alias_type": a.alias_type,
                "framing_note": a.framing_note,
            }
            for a in e.aliases
        ],
        "series": [{"day": d.date(), "articles": n} for d, n in series],
        "targeted_sentiment_by_operating_base": base_dist,
        "targeted_sentiment_examples": [
            {
                "sentiment": r[0],
                "score": r[1],
                "evidence_sentence": r[2],
                "confidence": r[3],
                "method": r[4],
                "article_id": r[5],
                "title": r[6],
                "source": r[7],
                "operating_base": r[8],
                "is_demo": r[9],
            }
            for r in examples
        ],
        "terminology": [
            {
                "term": r[0],
                "language": r[1],
                "alias_type": r[2],
                "framing_note": r[3],
                "operating_base": r[4],
                "mentions": r[5],
            }
            for r in terms
        ],
        "co_mentioned": [{"slug": r[0], "name_en": r[1], "name_ar": r[2], "articles": r[3]} for r in co],
        "recent_articles": recent,
    }


@router.get("/terminology", summary="Which names outlets use for an actor, by source")
def terminology(
    db: DB, f: F, entity: Annotated[str, Query(description="Entity slug, e.g. ansar-allah")]
) -> dict:
    e = db.scalar(select(m.Entity).where(m.Entity.slug == entity))
    if e is None:
        raise HTTPException(404, "entity not found")
    ids = apply_filters(select(m.Article.id), f).subquery()
    rows = db.execute(
        select(
            m.Source.slug,
            m.Source.name,
            m.Source.operating_base,
            m.Source.source_group,
            m.EntityAlias.surface_form,
            m.EntityAlias.alias_type,
            func.count(),
        )
        .join(m.EntityMention, m.EntityMention.alias_id == m.EntityAlias.id)
        .join(m.Article, m.Article.id == m.EntityMention.article_id)
        .join(m.Source, m.Source.id == m.Article.source_id)
        .where(m.EntityMention.entity_id == e.id, m.EntityMention.article_id.in_(select(ids.c.id)))
        .group_by(m.Source.id, m.EntityAlias.id)
    ).all()
    by_source: dict[str, dict] = {}
    for slug, name, base, group, term, atype, n in rows:
        d = by_source.setdefault(
            slug, {"source": slug, "name": name, "operating_base": base, "source_group": group, "terms": []}
        )
        d["terms"].append({"term": term, "alias_type": atype, "mentions": n})
    for d in by_source.values():
        d["terms"].sort(key=lambda x: -x["mentions"])
    return {
        "entity": e.slug,
        "name_en": e.name_en,
        "aliases": [
            {
                "surface_form": a.surface_form,
                "language": a.language,
                "alias_type": a.alias_type,
                "framing_note": a.framing_note,
            }
            for a in e.aliases
        ],
        "by_source": sorted(by_source.values(), key=lambda d: -sum(t["mentions"] for t in d["terms"])),
    }
