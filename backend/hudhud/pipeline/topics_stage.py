"""Stage 4: topic models (global + per top-level category), incremental assignment,
cross-model alignment to persistent global topics, optional LLM labels."""

from __future__ import annotations

import datetime as dt

import numpy as np
import structlog
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from hudhud.config import get_settings
from hudhud.db import models as m
from hudhud.nlp.embeddings import get_embedder
from hudhud.nlp.registry import model_version_id
from hudhud.nlp.topics import assign_incremental, fit_topics, keyword_label

log = structlog.get_logger()
TRAINING_DAYS = 90
MAX_DOCS = 20000
ALIGN_THRESHOLD = {True: 0.85, False: 0.6}  # semantic vs hashing embeddings


def _corpus(session: Session, embed_mv: int, since: dt.datetime, category_root: int | None = None):
    q = (
        select(
            m.Article.id, m.Article.title, m.Article.excerpt, m.Article.language, m.ArticleEmbedding.embedding
        )
        .join(m.ArticleEmbedding, m.ArticleEmbedding.article_id == m.Article.id)
        .where(
            m.ArticleEmbedding.model_version_id == embed_mv,
            m.Article.published_at >= since,
            m.Article.duplicate_of_id.is_(None),
            m.Article.is_syndicated.is_(False),
            m.Article.deleted_at.is_(None),
        )
    )
    if category_root is not None:
        cat_ids = select(m.Category.id).where(
            (m.Category.id == category_root) | (m.Category.parent_id == category_root)
        )
        q = q.join(m.CategoryAssignment, m.CategoryAssignment.article_id == m.Article.id).where(
            m.CategoryAssignment.is_current.is_(True),
            m.CategoryAssignment.rank == "primary",
            m.CategoryAssignment.category_id.in_(cat_ids),
        )
    rows = session.execute(q.order_by(m.Article.published_at.desc()).limit(MAX_DOCS)).all()
    ids = [r[0] for r in rows]
    docs = [f"{r[1]}. {r[2] or ''}" for r in rows]
    langs = [r[3] or "unknown" for r in rows]
    emb = (
        np.asarray([np.asarray(r[4], dtype=np.float32) for r in rows])
        if rows
        else np.zeros((0, 384), np.float32)
    )
    return ids, docs, langs, emb


def _needs_refit(session: Session, scope: str, n_docs: int) -> bool:
    current = session.scalar(
        select(m.TopicModel)
        .where(m.TopicModel.scope == scope, m.TopicModel.status == "active")
        .order_by(m.TopicModel.created_at.desc())
    )
    if current is None:
        return True
    age = dt.datetime.now(dt.UTC) - current.created_at
    return age.days >= get_settings().topic_full_retrain_days or n_docs > 1.3 * max(current.document_count, 1)


def _align(session: Session, topic: m.Topic, centroid: np.ndarray, semantic: bool) -> None:
    gts = session.execute(
        select(m.GlobalTopic.id, m.GlobalTopic.centroid).where(m.GlobalTopic.centroid.is_not(None))
    ).all()
    best_id, best_sim = None, -1.0
    for gid, c in gts:
        sim = float(np.dot(np.asarray(c, dtype=np.float32), centroid))
        if sim > best_sim:
            best_id, best_sim = gid, sim
    if best_id is not None and best_sim >= ALIGN_THRESHOLD[semantic]:
        session.merge(
            m.TopicAlignment(
                topic_id=topic.id,
                global_topic_id=best_id,
                confidence=round(best_sim, 4),
                method="centroid_cosine",
            )
        )
        return
    gt = m.GlobalTopic(label_en=topic.label, centroid=centroid.tolist())
    session.add(gt)
    session.flush()
    session.add(
        m.TopicAlignment(topic_id=topic.id, global_topic_id=gt.id, confidence=1.0, method="new_global_topic")
    )


def fit_scope(
    session: Session, scope: str, ids, docs, langs, emb, embed_mv: int, semantic: bool, since
) -> m.TopicModel | None:
    if len(ids) < get_settings().topic_min_docs:
        return None
    fit = fit_topics(docs, emb, semantic)
    for old in session.scalars(
        select(m.TopicModel).where(m.TopicModel.scope == scope, m.TopicModel.status == "active")
    ):
        old.status = "superseded"
    tm = m.TopicModel(
        name=f"{scope} {dt.date.today().isoformat()}",
        scope=scope,
        algorithm=fit.algorithm,
        embedding_model_version_id=embed_mv,
        parameters=fit.parameters | {"semantic_embeddings": semantic},
        training_start=since,
        training_end=dt.datetime.now(dt.UTC),
        document_count=len(ids),
        metrics=fit.metrics,
        status="active",
    )
    session.add(tm)
    session.flush()
    for ft in fit.topics:
        rows = ft.member_rows
        lang_dist: dict[str, int] = {}
        for r in rows:
            lang_dist[langs[r]] = lang_dist.get(langs[r], 0) + 1
        sims = emb[rows] @ ft.centroid
        reps = [ids[rows[i]] for i in np.argsort(-sims)[:5]]
        topic = m.Topic(
            topic_model_id=tm.id,
            topic_index=ft.index,
            raw_representation=[list(t) for t in ft.terms],
            label=keyword_label(ft.terms),
            label_method="keywords",
            size=ft.size,
            language_distribution=lang_dist,
            representative_article_ids=reps,
            centroid=ft.centroid.tolist(),
            quality={
                "coherence_npmi": ft.coherence,
                "assign_threshold": round(ft.assign_threshold, 4),
                "size": ft.size,
                "weak": (ft.coherence is not None and ft.coherence < 0) or ft.size < 5,
            },
        )
        session.add(topic)
        session.flush()
        if scope == "global":  # persistent concepts track the global model across refits
            _align(session, topic, ft.centroid, semantic)
        for r in rows:
            session.add(
                m.TopicAssignment(
                    article_id=ids[r],
                    topic_id=topic.id,
                    topic_model_id=tm.id,
                    probability=round(float(fit.probabilities[r]), 4),
                    method="fit",
                )
            )
    session.flush()
    return tm


def assign_new(session: Session, scope: str, embed_mv: int) -> int:
    tm = session.scalar(
        select(m.TopicModel)
        .where(m.TopicModel.scope == scope, m.TopicModel.status == "active")
        .order_by(m.TopicModel.created_at.desc())
    )
    if tm is None:
        return 0
    topics = list(
        session.scalars(select(m.Topic).where(m.Topic.topic_model_id == tm.id).order_by(m.Topic.id))
    )
    if not topics:
        return 0
    assigned = select(m.TopicAssignment.article_id).where(m.TopicAssignment.topic_model_id == tm.id)
    rows = session.execute(
        select(m.ArticleEmbedding.article_id, m.ArticleEmbedding.embedding)
        .join(m.Article, m.Article.id == m.ArticleEmbedding.article_id)
        .where(
            m.ArticleEmbedding.model_version_id == embed_mv,
            m.Article.id.not_in(assigned),
            m.Article.duplicate_of_id.is_(None),
            m.Article.published_at >= tm.training_end - dt.timedelta(days=3),
        )
    ).all()
    if not rows:
        return 0
    emb = np.asarray([np.asarray(r[1], dtype=np.float32) for r in rows])
    cents = np.asarray([np.asarray(t.centroid, dtype=np.float32) for t in topics])
    thr = np.asarray([float((t.quality or {}).get("assign_threshold", 0.0)) for t in topics])
    n = 0
    for (aid, _), (j, sim) in zip(rows, assign_incremental(emb, cents, thr), strict=True):
        if j >= 0:
            session.add(
                m.TopicAssignment(
                    article_id=aid,
                    topic_id=topics[j].id,
                    topic_model_id=tm.id,
                    probability=round(sim, 4),
                    method="transform",
                )
            )
            n += 1
    session.flush()
    return n


def label_with_llm(session: Session, tm: m.TopicModel, max_topics: int = 30) -> int:
    try:
        from hudhud.llm.client import LLMClient

        llm = LLMClient(session)
    except Exception:
        return 0
    n = 0
    mv = model_version_id(session, get_settings().llm_model, "topic_label-1.0", provider="anthropic")
    for t in session.scalars(
        select(m.Topic).where(m.Topic.topic_model_id == tm.id).order_by(m.Topic.size.desc()).limit(max_topics)
    ):
        heads = session.scalars(
            select(m.Article.title).where(m.Article.id.in_(t.representative_article_ids))
        ).all()
        out = llm.call(
            "topic_label",
            terms=", ".join(f"{w} ({s})" for w, s in t.raw_representation[:10]),
            headlines="\n".join(f"- {h}" for h in heads),
        )
        if out is None:
            continue
        t.label, t.label_method, t.llm_description = out.label_en, "llm", out.description
        session.merge(m.TopicTranslation(topic_id=t.id, language="ar", label=out.label_ar, method="llm"))
        t.quality = (t.quality or {}) | {"llm_label_confidence": out.confidence, "llm_model_version_id": mv}
        n += 1
    return n


def run_topics(session: Session, force_refit: bool = False) -> dict:
    embedder = get_embedder()
    semantic = getattr(embedder, "semantic", False)
    embed_mv = model_version_id(
        session,
        embedder.name,
        embedder.version,
        {"dim": embedder.dim},
        provider="huggingface" if semantic else "internal",
    )
    since = dt.datetime.now(dt.UTC) - dt.timedelta(days=TRAINING_DAYS)
    out = {"refit": [], "assigned": 0, "llm_labels": 0}
    scopes: list[tuple[str, int | None]] = [("global", None)]
    roots = session.execute(
        select(m.Category.id, m.Category.slug).where(m.Category.parent_id.is_(None))
    ).all()
    scopes += [(f"category:{slug}", cid) for cid, slug in roots]
    for scope, root in scopes:
        ids, docs, langs, emb = _corpus(session, embed_mv, since, root)
        if force_refit or _needs_refit(session, scope, len(ids)):
            tm = fit_scope(session, scope, ids, docs, langs, emb, embed_mv, semantic, since)
            if tm is not None:
                out["refit"].append({"scope": scope, "docs": len(ids), **tm.metrics})
                if scope == "global":
                    out["llm_labels"] += label_with_llm(session, tm)
        else:
            out["assigned"] += assign_new(session, scope, embed_mv)
        session.commit()
    out["topic_models_active"] = session.scalar(
        select(func.count()).select_from(m.TopicModel).where(m.TopicModel.status == "active")
    )
    log.info("topics_done", refits=len(out["refit"]), assigned=out["assigned"])
    return out
