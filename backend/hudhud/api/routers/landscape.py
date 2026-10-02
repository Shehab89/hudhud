"""Media ecosystem graph and narrative comparison across outlet groupings."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from hudhud.api.deps import DB, F, apply_filters
from hudhud.db import models as m

router = APIRouter(tags=["landscape"])

GROUP_COLUMNS = {
    "operating_base": m.Source.operating_base,
    "source_group": m.Source.source_group,
    "language": m.Article.language,
}


@router.get(
    "/media-landscape", summary="Outlet network: nodes are sources, edges are shared stories and syndication"
)
def media_landscape(db: DB, f: F, min_shared: Annotated[int, Query(ge=1, le=100)] = 2) -> dict:
    ids = apply_filters(select(m.Article.id), f, dedupe=False).subquery()
    A = m.Article
    nodes = db.execute(
        select(
            m.Source.id,
            m.Source.slug,
            m.Source.name,
            m.Source.source_group,
            m.Source.operating_base,
            m.Source.country,
            m.Source.is_demo,
            func.count(A.id),
            func.count(func.distinct(A.story_cluster_id)),
        )
        .join(A, A.source_id == m.Source.id)
        .where(A.id.in_(select(ids.c.id)))
        .group_by(m.Source.id)
    ).all()
    pairs = (
        select(A.source_id.label("s"), A.story_cluster_id.label("c"))
        .where(A.id.in_(select(ids.c.id)), A.story_cluster_id.is_not(None))
        .distinct()
        .subquery()
    )
    p1, p2 = pairs.alias("p1"), pairs.alias("p2")
    shared = db.execute(
        select(p1.c.s, p2.c.s, func.count())
        .join(p2, (p1.c.c == p2.c.c) & (p1.c.s < p2.c.s))
        .group_by(p1.c.s, p2.c.s)
        .having(func.count() >= min_shared)
    ).all()
    R, B = m.ArticleRelation, m.Article.__table__.alias("b")
    synd = db.execute(
        select(A.source_id, B.c.source_id, func.count())
        .join(R, R.from_article_id == A.id)
        .join(B, B.c.id == R.to_article_id)
        .where(R.relation_type == "syndicated_from", A.id.in_(select(ids.c.id)), A.source_id != B.c.source_id)
        .group_by(A.source_id, B.c.source_id)
    ).all()
    orient = dict(
        db.execute(
            select(m.SourceOrientation.source_id, m.SourceOrientation.simplified).where(
                m.SourceOrientation.valid_to.is_(None)
            )
        ).all()
    )
    slug = {n[0]: n[1] for n in nodes}
    stories = {n[0]: n[8] for n in nodes}
    return {
        "note": "Edges show which outlets covered the same stories (co-coverage) or republished each other's copy "
        "(syndication). Proximity in this graph is about coverage overlap, not political agreement.",
        "nodes": [
            {
                "id": n[1],
                "name": n[2],
                "source_group": n[3],
                "operating_base": n[4],
                "country": n[5],
                "is_demo": n[6],
                "articles": n[7],
                "stories": n[8],
                "orientation": orient.get(n[0]),
            }
            for n in nodes
        ],
        "edges": [
            {
                "source": slug[a],
                "target": slug[b],
                "type": "co_coverage",
                "shared_stories": n,
                "jaccard": round(n / max(1, stories[a] + stories[b] - n), 4),
            }
            for a, b, n in shared
            if a in slug and b in slug
        ]
        + [
            {"source": slug[a], "target": slug[b], "type": "syndication", "articles": n}
            for a, b, n in synd
            if a in slug and b in slug
        ],
    }


@router.get(
    "/compare/narratives", summary="Compare frames, sentiment, terminology and actors across outlet groups"
)
def compare_narratives(
    db: DB, f: F, group_by: Literal["operating_base", "source_group", "language"] = "operating_base"
) -> dict:
    """Restrict with the usual filters (category, entity, dates...) and compare how groups cover it."""
    ids = apply_filters(select(m.Article.id), f).subquery()
    in_ids = select(ids.c.id)
    col = GROUP_COLUMNS[group_by]
    A = m.Article

    def grouped(stmt):
        return stmt.select_from(A).join(m.Source, m.Source.id == A.source_id).where(A.id.in_(in_ids))

    totals = dict(db.execute(grouped(select(col, func.count(A.id))).group_by(col)).all())
    out: dict[str, dict] = {
        str(g): {"articles": n, "frames": {}, "sentiment": {}, "tone": {}, "terminology": [], "actors": []}
        for g, n in totals.items()
    }
    for g, slug, n in db.execute(
        grouped(select(col, m.Frame.slug, func.count()))
        .join(
            m.FramingAnalysis, (m.FramingAnalysis.article_id == A.id) & m.FramingAnalysis.is_current.is_(True)
        )
        .join(m.Frame, m.Frame.id == m.FramingAnalysis.frame_id)
        .group_by(col, m.Frame.slug)
    ).all():
        out[str(g)]["frames"][slug] = round(n / totals[g], 4)
    for g, pol, n in db.execute(
        grouped(select(col, m.SentimentAnalysis.polarity, func.count()))
        .join(
            m.SentimentAnalysis,
            (m.SentimentAnalysis.article_id == A.id) & m.SentimentAnalysis.is_current.is_(True),
        )
        .group_by(col, m.SentimentAnalysis.polarity)
    ).all():
        out[str(g)]["sentiment"][pol] = round(n / totals[g], 4)
    for g, tone, n in db.execute(
        grouped(select(col, m.EmotionAnalysis.dominant, func.count()))
        .join(
            m.EmotionAnalysis,
            (m.EmotionAnalysis.article_id == A.id)
            & m.EmotionAnalysis.is_current.is_(True)
            & (m.EmotionAnalysis.kind == "tone"),
        )
        .group_by(col, m.EmotionAnalysis.dominant)
    ).all():
        out[str(g)]["tone"][tone or "none"] = round(n / totals[g], 4)
    for g, ent, term, atype, n in db.execute(
        grouped(
            select(col, m.Entity.slug, m.EntityAlias.surface_form, m.EntityAlias.alias_type, func.count())
        )
        .join(m.EntityMention, m.EntityMention.article_id == A.id)
        .join(m.EntityAlias, m.EntityAlias.id == m.EntityMention.alias_id)
        .join(m.Entity, m.Entity.id == m.EntityMention.entity_id)
        .where(m.Entity.entity_type.not_in(["location", "country"]))
        .group_by(col, m.Entity.slug, m.EntityAlias.id)
        .order_by(func.count().desc())
    ).all():
        if len(out[str(g)]["terminology"]) < 15:
            out[str(g)]["terminology"].append(
                {"entity": ent, "term": term, "alias_type": atype, "mentions": n}
            )
    for g, ent, name, n, ts in db.execute(
        grouped(
            select(
                col,
                m.Entity.slug,
                m.Entity.name_en,
                func.count(func.distinct(A.id)),
                func.avg(m.TargetedSentiment.score),
            )
        )
        .join(m.EntityMention, m.EntityMention.article_id == A.id)
        .join(m.Entity, m.Entity.id == m.EntityMention.entity_id)
        .outerjoin(
            m.TargetedSentiment,
            (m.TargetedSentiment.article_id == A.id)
            & (m.TargetedSentiment.entity_id == m.Entity.id)
            & m.TargetedSentiment.is_current.is_(True),
        )
        .where(m.Entity.entity_type.not_in(["location", "country"]))
        .group_by(col, m.Entity.id)
        .order_by(func.count(func.distinct(A.id)).desc())
    ).all():
        if len(out[str(g)]["actors"]) < 10:
            out[str(g)]["actors"].append(
                {
                    "slug": ent,
                    "name_en": name,
                    "share": round(n / totals[g], 4),
                    "mean_targeted_sentiment": round(float(ts), 3) if ts is not None else None,
                }
            )
    frames = {
        fr.slug: {"name_en": fr.name_en, "name_ar": fr.name_ar, "description": fr.description}
        for fr in db.scalars(select(m.Frame))
    }
    return {
        "filters": f.as_dict(),
        "group_by": group_by,
        "frames": frames,
        "groups": out,
        "note": "Shares are the fraction of each group's articles with that frame / polarity / tone. Small groups "
        "give unstable shares; check the article counts before comparing.",
    }
