"""Articles: listing, per-article analysis with provenance, and hybrid search."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, or_, select

from observatory.api.deps import DB, F, Page, apply_filters
from observatory.api.schemas import ArticleSummary, Paged
from observatory.api.util import article_summaries, prov, provenance_map
from observatory.db import models as m
from observatory.nlp.text import normalize_for_matching

router = APIRouter(tags=["articles"])


@router.get("/articles", response_model=Paged[ArticleSummary], summary="List articles matching the filters")
def list_articles(
    db: DB,
    f: F,
    page: Page,
    q: Annotated[str | None, Query(max_length=200, description="Keyword query (title + excerpt).")] = None,
    include_duplicates: bool = False,
    sort: Literal["newest", "oldest"] = "newest",
) -> Paged[ArticleSummary]:
    A = m.Article
    stmt = apply_filters(select(A), f, dedupe=not include_duplicates)
    if q:
        stmt = stmt.where(
            A.search_tsv.op("@@")(func.websearch_to_tsquery("simple", normalize_for_matching(q)))
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    order = A.published_at.desc() if sort == "newest" else A.published_at.asc()
    limit, offset = page
    items = article_summaries(db, db.scalars(stmt.order_by(order, A.id.desc()).limit(limit).offset(offset)))
    return Paged(
        total=total, limit=limit, offset=offset, items=items, contains_demo=any(i.is_demo for i in items)
    )


@router.get("/articles/{article_id}", summary="One article with every analysis result and its provenance")
def get_article(db: DB, article_id: int) -> dict:
    a = db.get(m.Article, article_id)
    if a is None or a.deleted_at is not None:
        raise HTTPException(404, "article not found")
    src = db.get(m.Source, a.source_id)

    def cur(model):
        return list(db.scalars(select(model).where(model.article_id == a.id, model.is_current.is_(True))))

    cats, sents, emos = cur(m.CategoryAssignment), cur(m.SentimentAnalysis), cur(m.EmotionAnalysis)
    frames, targeted = cur(m.FramingAnalysis), cur(m.TargetedSentiment)
    pm = provenance_map(db, [r.model_version_id for r in [*cats, *sents, *emos, *frames, *targeted]])
    cat_rows = {
        c.id: c
        for c in db.scalars(select(m.Category).where(m.Category.id.in_([c.category_id for c in cats])))
    }
    frame_rows = {
        fr.id: fr for fr in db.scalars(select(m.Frame).where(m.Frame.id.in_([x.frame_id for x in frames])))
    }
    ents = {
        e.id: e
        for e in db.scalars(
            select(m.Entity).where(
                m.Entity.id.in_(select(m.EntityMention.entity_id).where(m.EntityMention.article_id == a.id))
            )
        )
    }
    mentions = db.execute(
        select(m.EntityMention, m.EntityAlias.alias_type, m.EntityAlias.framing_note)
        .outerjoin(m.EntityAlias, m.EntityAlias.id == m.EntityMention.alias_id)
        .where(m.EntityMention.article_id == a.id)
        .order_by(m.EntityMention.start_char)
    ).all()
    events = db.execute(
        select(m.Event, m.EventMention.evidence_sentence, m.EventMention.trigger)
        .join(m.EventMention, m.EventMention.event_id == m.Event.id)
        .where(m.EventMention.article_id == a.id)
    ).all()
    topics = db.execute(
        select(m.Topic.id, m.Topic.label, m.TopicModel.scope, m.TopicAssignment.probability)
        .join(m.TopicAssignment, m.TopicAssignment.topic_id == m.Topic.id)
        .join(m.TopicModel, m.TopicModel.id == m.Topic.topic_model_id)
        .where(m.TopicAssignment.article_id == a.id, m.TopicModel.status == "active")
    ).all()
    rel = db.execute(
        select(
            m.ArticleRelation.relation_type,
            m.ArticleRelation.similarity_score,
            m.ArticleRelation.method,
            m.Article.id,
            m.Article.title,
            m.Source.name,
            m.Article.is_demo,
        )
        .join(m.Article, m.Article.id == m.ArticleRelation.to_article_id)
        .join(m.Source, m.Source.id == m.Article.source_id)
        .where(m.ArticleRelation.from_article_id == a.id)
        .limit(20)
    ).all()
    cluster = db.get(m.StoryCluster, a.story_cluster_id) if a.story_cluster_id else None
    orientation = db.scalar(
        select(m.SourceOrientation).where(
            m.SourceOrientation.source_id == src.id, m.SourceOrientation.valid_to.is_(None)
        )
    )
    return {
        "id": a.id,
        "is_demo": a.is_demo,
        "title": a.title,
        "url": a.url,
        "canonical_url": a.canonical_url,
        "excerpt": a.excerpt,
        "published_at": a.published_at,
        "published_at_estimated": a.published_at_estimated,
        "author": a.author,
        "publisher_name": a.publisher_name,
        "language": {
            "code": a.language,
            "confidence": a.language_confidence,
            "script": a.script,
            "mixed": a.is_mixed_language,
            "method": (a.raw_metadata or {}).get("language_method"),
        },
        "quality": {
            "score": a.quality_score,
            "detail": a.quality_detail,
            "note": "Technical completeness of the record only; not a credibility rating.",
        },
        "source": {
            "slug": src.slug,
            "name": src.name,
            "source_group": src.source_group,
            "operating_base": src.operating_base,
            "is_demo": src.is_demo,
            "orientation": {
                "simplified": orientation.simplified,
                "confidence": orientation.confidence,
                "method": orientation.method,
            }
            if orientation
            else None,
        },
        # A: source orientation lives on the source. B-E below are separate per-article analyses.
        "sentiment": [
            {"polarity": s.polarity, "scores": s.scores, "intensity": s.intensity, **prov(s, pm)}
            for s in sents
        ],
        "emotions": [
            {"kind": e.kind, "dominant": e.dominant, "scores": e.scores, **prov(e, pm)} for e in emos
        ],
        "categories": [
            {
                "slug": cat_rows[c.category_id].slug,
                "name_en": cat_rows[c.category_id].name_en,
                "name_ar": cat_rows[c.category_id].name_ar,
                "rank": c.rank,
                "score": c.score,
                "route": c.route,
                "evidence": c.evidence,
                **prov(c, pm),
            }
            for c in sorted(cats, key=lambda c: -c.score)
        ],
        "frames": [
            {
                "slug": frame_rows[x.frame_id].slug,
                "name_en": frame_rows[x.frame_id].name_en,
                "name_ar": frame_rows[x.frame_id].name_ar,
                "score": x.score,
                "evidence_sentence": x.evidence_sentence,
                **prov(x, pm),
            }
            for x in frames
        ],
        "targeted_sentiment": [
            {
                "entity": ents[t.entity_id].slug if t.entity_id in ents else None,
                "entity_name": ents[t.entity_id].name_en if t.entity_id in ents else None,
                "sentiment": t.sentiment,
                "score": t.score,
                "evidence_sentence": t.evidence_sentence,
                **prov(t, pm),
            }
            for t in targeted
        ],
        "mentions": [
            {
                "entity": ents[mm.entity_id].slug if mm.entity_id in ents else None,
                "entity_type": ents[mm.entity_id].entity_type if mm.entity_id in ents else None,
                "surface_form": mm.surface_form,
                "field": mm.field,
                "start": mm.start_char,
                "end": mm.end_char,
                "alias_type": at,
                "framing_note": fn,
                "method": mm.method,
            }
            for mm, at, fn in mentions
        ],
        "events": [
            {
                "id": ev.id,
                "type": ev.event_type,
                "date": ev.event_date,
                "title": ev.title,
                "confidence": ev.confidence,
                "evidence_sentence": evid,
                "trigger": trig,
            }
            for ev, evid, trig in events
        ],
        "topics": [{"id": t[0], "label": t[1], "scope": t[2], "probability": t[3]} for t in topics],
        "relations": [
            {
                "type": r[0],
                "similarity": r[1],
                "method": r[2],
                "article_id": r[3],
                "title": r[4],
                "source": r[5],
                "is_demo": r[6],
            }
            for r in rel
        ],
        "story_cluster": {
            "id": cluster.id,
            "article_count": cluster.article_count,
            "source_count": cluster.source_count,
            "independent_source_count": cluster.independent_source_count,
            "language_count": cluster.language_count,
        }
        if cluster
        else None,
        "duplicate_of_id": a.duplicate_of_id,
        "is_syndicated": a.is_syndicated,
        "processing_status": a.processing_status,
    }


@router.get(
    "/stories/{cluster_id}", summary="All articles in a story cluster (cross-outlet coverage of one story)"
)
def story(db: DB, cluster_id: int) -> dict:
    c = db.get(m.StoryCluster, cluster_id)
    if c is None:
        raise HTTPException(404, "story not found")
    arts = db.scalars(
        select(m.Article)
        .where(m.Article.story_cluster_id == c.id, m.Article.deleted_at.is_(None))
        .order_by(m.Article.published_at)
    )
    return {
        "id": c.id,
        "article_count": c.article_count,
        "source_count": c.source_count,
        "independent_source_count": c.independent_source_count,
        "language_count": c.language_count,
        "first_seen_at": c.first_seen_at,
        "last_seen_at": c.last_seen_at,
        "articles": article_summaries(db, arts),
    }


@lru_cache
def _query_embedder():
    from observatory.nlp.embeddings import get_embedder

    return get_embedder()


def _embedding_mv(db: DB, emb) -> int | None:
    return db.scalar(
        select(m.ModelVersion.id)
        .join(m.Model, m.Model.id == m.ModelVersion.model_id)
        .where(m.Model.name == emb.name, m.ModelVersion.version == emb.version)
    )


@router.get("/search", summary="Hybrid search: keyword (full text) + semantic (embeddings), fused with RRF")
def search(
    db: DB,
    f: F,
    q: Annotated[str, Query(min_length=2, max_length=300)],
    mode: Literal["hybrid", "keyword", "semantic"] = "hybrid",
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> dict:
    A = m.Article
    ranked: dict[str, list[int]] = {}
    if mode in ("hybrid", "keyword"):
        tsq = func.websearch_to_tsquery("simple", normalize_for_matching(q))
        stmt = apply_filters(select(A.id), f).where(A.search_tsv.op("@@")(tsq))
        stmt = stmt.order_by(func.ts_rank_cd(A.search_tsv, tsq).desc()).limit(200)
        ranked["keyword"] = list(db.scalars(stmt))
        if not ranked["keyword"]:  # fall back to substring match for very short / unusual queries
            pat = f"%{normalize_for_matching(q)}%"
            ranked["keyword"] = list(
                db.scalars(
                    apply_filters(select(A.id), f)
                    .where(or_(A.title_normalized.ilike(pat), A.excerpt_normalized.ilike(pat)))
                    .limit(200)
                )
            )
    semantic_info = None
    if mode in ("hybrid", "semantic"):
        emb = _query_embedder()
        mv = _embedding_mv(db, emb)
        semantic_info = {
            "model": emb.name,
            "version": emb.version,
            "semantic": getattr(emb, "semantic", False),
        }
        if mv is not None:
            vec = emb.embed_queries([q])[0].tolist()
            dist = m.ArticleEmbedding.embedding.cosine_distance(vec)
            stmt = apply_filters(
                select(A.id).join(m.ArticleEmbedding, m.ArticleEmbedding.article_id == A.id), f
            )
            stmt = stmt.where(m.ArticleEmbedding.model_version_id == mv).order_by(dist).limit(200)
            ranked["semantic"] = list(db.scalars(stmt))
    scores: dict[int, float] = {}
    for ids in ranked.values():
        for rank, aid in enumerate(ids):
            scores[aid] = scores.get(aid, 0.0) + 1.0 / (60 + rank + 1)  # reciprocal rank fusion
    top = sorted(scores, key=lambda i: -scores[i])[:limit]
    arts = {a.id: a for a in db.scalars(select(A).where(A.id.in_(top)))}
    items = article_summaries(db, [arts[i] for i in top if i in arts])
    return {
        "query": q,
        "mode": mode,
        "semantic_model": semantic_info,
        "total": len(scores),
        "items": [
            {
                **i.model_dump(),
                "score": round(scores[i.id], 5),
                "matched_by": [k for k, v in ranked.items() if i.id in v],
            }
            for i in items
        ],
        "contains_demo": any(i.is_demo for i in items),
    }
