"""Small helpers shared by routers."""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from hudhud.api.deps import Filters, apply_filters
from hudhud.api.schemas import ArticleSummary, SourceRef
from hudhud.db import models as m


def article_summaries(db: Session, articles: Iterable[m.Article]) -> list[ArticleSummary]:
    arts = list(articles)
    if not arts:
        return []
    ids = [a.id for a in arts]
    sources = {
        s.id: s for s in db.scalars(select(m.Source).where(m.Source.id.in_({a.source_id for a in arts})))
    }
    cats = dict(
        db.execute(
            select(m.CategoryAssignment.article_id, m.Category.slug)
            .join(m.Category, m.Category.id == m.CategoryAssignment.category_id)
            .where(
                m.CategoryAssignment.article_id.in_(ids),
                m.CategoryAssignment.is_current.is_(True),
                m.CategoryAssignment.rank == "primary",
            )
        ).all()
    )
    sents = dict(
        db.execute(
            select(m.SentimentAnalysis.article_id, m.SentimentAnalysis.polarity).where(
                m.SentimentAnalysis.article_id.in_(ids), m.SentimentAnalysis.is_current.is_(True)
            )
        ).all()
    )
    return [
        ArticleSummary(
            id=a.id,
            title=a.title,
            url=a.url,
            published_at=a.published_at,
            language=a.language,
            excerpt=a.excerpt,
            source=SourceRef.model_validate(sources[a.source_id]),
            publisher_name=a.publisher_name,
            is_demo=a.is_demo,
            is_syndicated=a.is_syndicated,
            story_cluster_id=a.story_cluster_id,
            primary_category=cats.get(a.id),
            sentiment=sents.get(a.id),
        )
        for a in arts
    ]


def article_ids_subquery(f: Filters):
    return apply_filters(select(m.Article.id), f).subquery()


def count_articles(db: Session, f: Filters) -> int:
    return db.scalar(apply_filters(select(func.count(m.Article.id)), f)) or 0


def provenance_map(db: Session, mv_ids: Iterable[int | None]) -> dict[int, tuple[str, str]]:
    ids = {i for i in mv_ids if i}
    if not ids:
        return {}
    rows = db.execute(
        select(m.ModelVersion.id, m.Model.name, m.ModelVersion.version)
        .join(m.Model, m.Model.id == m.ModelVersion.model_id)
        .where(m.ModelVersion.id.in_(ids))
    ).all()
    return {r[0]: (r[1], r[2]) for r in rows}


def prov(row, pm: dict[int, tuple[str, str]]) -> dict:
    name, ver = pm.get(row.model_version_id, (None, None))
    return {
        "method": row.method,
        "model": name,
        "model_version": ver,
        "confidence": round(row.confidence, 4) if row.confidence is not None else None,
        "analysis_version": row.analysis_version,
    }
