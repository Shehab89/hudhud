"""Data-driven topics from the active topic models."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from observatory.api.deps import DB, F, apply_filters
from observatory.api.util import article_summaries
from observatory.db import models as m

router = APIRouter(tags=["topics"])


def _model(db: DB, scope: str) -> m.TopicModel | None:
    return db.scalar(
        select(m.TopicModel)
        .where(m.TopicModel.scope == scope, m.TopicModel.status == "active")
        .order_by(m.TopicModel.created_at.desc())
    )


@router.get("/topic-models", summary="Active topic models with their quality metrics")
def topic_models(db: DB) -> list[dict]:
    return [
        {
            "id": t.id,
            "scope": t.scope,
            "algorithm": t.algorithm,
            "documents": t.document_count,
            "metrics": t.metrics,
            "parameters": t.parameters,
            "training_start": t.training_start,
            "training_end": t.training_end,
            "created_at": t.created_at,
        }
        for t in db.scalars(
            select(m.TopicModel).where(m.TopicModel.status == "active").order_by(m.TopicModel.scope)
        )
    ]


@router.get("/topics", summary="Topics of the active model for a scope, with counts under the filters")
def list_topics(
    db: DB, f: F, scope: Annotated[str, Query(description="global or category:<slug>")] = "global"
) -> dict:
    tm = _model(db, scope)
    if tm is None:
        return {
            "scope": scope,
            "model": None,
            "topics": [],
            "note": "No topic model yet: it needs at least TOPIC_MIN_DOCS analysed articles.",
        }
    ids = apply_filters(select(m.Article.id), f).subquery()
    counts = dict(
        db.execute(
            select(m.TopicAssignment.topic_id, func.count())
            .where(
                m.TopicAssignment.topic_model_id == tm.id, m.TopicAssignment.article_id.in_(select(ids.c.id))
            )
            .group_by(m.TopicAssignment.topic_id)
        ).all()
    )
    ar = dict(
        db.execute(
            select(m.TopicTranslation.topic_id, m.TopicTranslation.label).where(
                m.TopicTranslation.language == "ar"
            )
        ).all()
    )
    topics = [
        {
            "id": t.id,
            "label": t.label,
            "label_ar": ar.get(t.id),
            "label_method": t.label_method,
            "terms": t.raw_representation[:10],
            "size": t.size,
            "count": counts.get(t.id, 0),
            "language_distribution": t.language_distribution,
            "quality": t.quality,
        }
        for t in db.scalars(select(m.Topic).where(m.Topic.topic_model_id == tm.id))
    ]
    return {
        "scope": scope,
        "model": {
            "id": tm.id,
            "algorithm": tm.algorithm,
            "metrics": tm.metrics,
            "documents": tm.document_count,
            "created_at": tm.created_at,
        },
        "topics": sorted(topics, key=lambda x: -x["count"]),
    }


@router.get("/topics/{topic_id}", summary="Topic profile: terms, label provenance, series, outlets, articles")
def get_topic(db: DB, f: F, topic_id: int) -> dict:
    t = db.get(m.Topic, topic_id)
    if t is None:
        raise HTTPException(404, "topic not found")
    tm = db.get(m.TopicModel, t.topic_model_id)
    ids = apply_filters(select(m.Article.id), f).subquery()
    members = select(m.TopicAssignment.article_id).where(
        m.TopicAssignment.topic_id == t.id, m.TopicAssignment.article_id.in_(select(ids.c.id))
    )
    in_topic = m.Article.id.in_(members)
    day = func.date_trunc("day", m.Article.published_at)
    series = db.execute(select(day, func.count()).where(in_topic).group_by(day).order_by(day)).all()
    by_source = db.execute(
        select(m.Source.slug, m.Source.name, m.Source.operating_base, func.count())
        .join(m.Article, m.Article.source_id == m.Source.id)
        .where(in_topic)
        .group_by(m.Source.id)
        .order_by(func.count().desc())
        .limit(15)
    ).all()
    sentiment = dict(
        db.execute(
            select(m.SentimentAnalysis.polarity, func.count())
            .where(m.SentimentAnalysis.is_current.is_(True), m.SentimentAnalysis.article_id.in_(members))
            .group_by(m.SentimentAnalysis.polarity)
        ).all()
    )
    reps = list(db.scalars(select(m.Article).where(m.Article.id.in_(t.representative_article_ids or []))))
    recent = list(
        db.scalars(select(m.Article).where(in_topic).order_by(m.Article.published_at.desc()).limit(20))
    )
    align = db.execute(
        select(m.GlobalTopic.id, m.GlobalTopic.label_en, m.TopicAlignment.confidence, m.TopicAlignment.method)
        .join(m.TopicAlignment, m.TopicAlignment.global_topic_id == m.GlobalTopic.id)
        .where(m.TopicAlignment.topic_id == t.id)
    ).first()
    ar = db.scalar(
        select(m.TopicTranslation.label).where(
            m.TopicTranslation.topic_id == t.id, m.TopicTranslation.language == "ar"
        )
    )
    return {
        "id": t.id,
        "label": t.label,
        "label_ar": ar,
        "label_method": t.label_method,
        "llm_description": t.llm_description,
        "terms": t.raw_representation,
        "size": t.size,
        "language_distribution": t.language_distribution,
        "quality": t.quality,
        "model": {"id": tm.id, "scope": tm.scope, "algorithm": tm.algorithm, "metrics": tm.metrics},
        "global_topic": {"id": align[0], "label": align[1], "confidence": align[2], "method": align[3]}
        if align
        else None,
        "series": [{"day": d.date(), "articles": n} for d, n in series],
        "top_sources": [
            {"slug": r[0], "name": r[1], "operating_base": r[2], "articles": r[3]} for r in by_source
        ],
        "sentiment": sentiment,
        "representative_articles": article_summaries(db, reps),
        "recent_articles": article_summaries(db, recent),
    }
