"""Stage 3: per-article NLP. Each result row records model version, method, confidence.

Skips articles whose content hash was already analysed (cache), and exact duplicates
(they point at the analysed original). Re-analysis marks earlier rows is_current=False
instead of deleting them, so historical results stay reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import structlog
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from hudhud.config import get_settings
from hudhud.db import models as m
from hudhud.nlp import affect
from hudhud.nlp.classify import TaxonomyClassifier, zero_shot_rerank
from hudhud.nlp.embeddings import article_text, get_embedder
from hudhud.nlp.events import extract_events
from hudhud.nlp.framing import FrameSpec, detect_frames
from hudhud.nlp.gazetteer import Gazetteer
from hudhud.nlp.registry import ANALYSIS_VERSION, model_version_id, use_transformers
from hudhud.pipeline.dedup import semantic_links

log = structlog.get_logger()
TARGET_TYPES = ("political_actor", "armed_group", "country", "igo", "person")


@dataclass
class Context:
    session: Session
    embedder: object
    embed_mv: int
    lexicon_mv: int
    gazetteer_mv: int
    events_mv: int
    sentiment_mv: int
    zero_shot_mv: int | None
    use_models: bool
    gazetteer: Gazetteer
    classifier: TaxonomyClassifier
    frames: list[FrameSpec]
    location_ids: set[int]
    llm: object | None = None
    llm_budget_left: int = 0
    stats: dict = field(
        default_factory=lambda: {"analysed": 0, "embedded": 0, "llm_reviews": 0, "uncertain": 0}
    )


def build_context(session: Session) -> Context:
    s = get_settings()
    embedder = get_embedder()
    use_models = use_transformers() and getattr(embedder, "semantic", False)
    embed_mv = model_version_id(
        session,
        embedder.name,
        embedder.version,
        {"dim": embedder.dim},
        provider="huggingface" if embedder.semantic else "internal",
    )
    lexicon_mv = model_version_id(session, "hudhud/lexicon", ANALYSIS_VERSION, provider="internal")
    gazetteer_mv = model_version_id(session, "hudhud/gazetteer", ANALYSIS_VERSION, provider="internal")
    events_mv = model_version_id(session, "hudhud/rule-events", ANALYSIS_VERSION, provider="internal")
    sentiment_mv = model_version_id(session, s.sentiment_model, "default") if use_models else lexicon_mv
    zero_shot_mv = model_version_id(session, s.zero_shot_model, "default") if use_models else None
    frames = [
        FrameSpec(
            f.id,
            f.slug,
            (f.cues or {}).get("hypothesis"),
            [t for k, v in (f.cues or {}).items() if k != "hypothesis" for t in v],
        )
        for f in session.scalars(select(m.Frame))
    ]
    location_ids = set(session.scalars(select(m.Location.entity_id)))
    llm = None
    try:
        from hudhud.llm.client import LLMClient

        llm = LLMClient(session)
    except Exception:
        llm = None
    return Context(
        session,
        embedder,
        embed_mv,
        lexicon_mv,
        gazetteer_mv,
        events_mv,
        sentiment_mv,
        zero_shot_mv,
        use_models,
        Gazetteer.from_db(session),
        TaxonomyClassifier.from_db(session, embedder),
        frames,
        location_ids,
        llm,
        s.llm_max_articles_per_run if llm else 0,
    )


def _retire(session: Session, model, article_id: int) -> None:
    session.execute(
        update(model)
        .where(model.article_id == article_id, model.is_current.is_(True))
        .values(is_current=False)
    )


def run_analyse(session: Session, run_id: int | None, batch_size: int = 64, limit: int | None = None) -> dict:
    ctx = build_context(session)
    q = (
        select(m.Article.id)
        .where(m.Article.processing_status == "deduped", m.Article.deleted_at.is_(None))
        .order_by(m.Article.id)
    )
    ids = list(session.scalars(q.limit(limit) if limit else q))
    for start in range(0, len(ids), batch_size):
        batch = [session.get(m.Article, i) for i in ids[start : start + batch_size]]
        _analyse_batch(ctx, batch, run_id)
        session.commit()
    log.info("analyse_done", **ctx.stats, models=ctx.use_models, embedder=ctx.embedder.name)
    return ctx.stats | {"embedder": ctx.embedder.name, "transformer_models": ctx.use_models}


def _analyse_batch(ctx: Context, batch: list[m.Article], run_id: int | None) -> None:
    session = ctx.session
    todo = [a for a in batch if a.duplicate_of_id is None and a.analysed_content_hash != a.content_hash]
    for a in batch:
        if a not in todo:
            a.processing_status = "analysed"
    if not todo:
        return
    # embeddings (cached by content hash)
    have = {
        aid: h
        for aid, h in session.execute(
            select(m.ArticleEmbedding.article_id, m.ArticleEmbedding.content_hash).where(
                m.ArticleEmbedding.article_id.in_([a.id for a in todo]),
                m.ArticleEmbedding.model_version_id == ctx.embed_mv,
            )
        )
    }
    need = [a for a in todo if have.get(a.id) != a.content_hash]
    vectors: dict[int, np.ndarray] = {}
    if need:
        vecs = ctx.embedder.embed_documents([article_text(a.title, a.excerpt) for a in need])
        for a, v in zip(need, vecs, strict=True):
            session.merge(
                m.ArticleEmbedding(
                    article_id=a.id,
                    model_version_id=ctx.embed_mv,
                    embedding=v.tolist(),
                    content_hash=a.content_hash,
                )
            )
            vectors[a.id] = v
        ctx.stats["embedded"] += len(need)
    for a in todo:
        if a.id not in vectors:
            emb = session.scalar(
                select(m.ArticleEmbedding.embedding).where(
                    m.ArticleEmbedding.article_id == a.id, m.ArticleEmbedding.model_version_id == ctx.embed_mv
                )
            )
            vectors[a.id] = np.asarray(emb, dtype=np.float32)
    session.flush()
    semantic_links(session, [a.id for a in todo], ctx.embed_mv, getattr(ctx.embedder, "semantic", False))

    for a in todo:
        try:
            with session.begin_nested():
                _analyse_article(ctx, a, vectors[a.id])
            a.processing_status = "analysed"
            a.analysed_content_hash = a.content_hash
            ctx.stats["analysed"] += 1
        except Exception as exc:
            log.warning("analyse_failed", article=a.id, error=str(exc)[:300])
            session.add(
                m.PipelineError(
                    run_id=run_id,
                    article_id=a.id,
                    source_id=a.source_id,
                    stage="analyse",
                    error_type=type(exc).__name__,
                    message=str(exc)[:2000],
                )
            )
            a.processing_status = "error"


def _analyse_article(ctx: Context, a: m.Article, vec: np.ndarray) -> None:
    session = ctx.session
    body = a.content_text or a.excerpt or ""
    text = f"{a.title}. {body}".strip()

    # earlier results stay in the table but stop being current
    for model in (
        m.CategoryAssignment,
        m.SentimentAnalysis,
        m.EmotionAnalysis,
        m.FramingAnalysis,
        m.TargetedSentiment,
    ):
        _retire(session, model, a.id)

    # ---- entities & locations (deterministic; replace on re-analysis)
    session.execute(delete(m.EntityMention).where(m.EntityMention.article_id == a.id))
    mentions = ctx.gazetteer.find(a.title, "title") + ctx.gazetteer.find(body, "excerpt")
    for mm in mentions:
        session.add(
            m.EntityMention(
                article_id=a.id,
                entity_id=mm.entity_id,
                alias_id=mm.alias_id,
                surface_form=mm.surface_form[:300],
                field=mm.field,
                start_char=mm.start,
                end_char=mm.end,
                sentence=mm.sentence[:1000],
                method="gazetteer",
                confidence=0.9,
                model_version_id=ctx.gazetteer_mv,
            )
        )

    # ---- categories (confidence-routed)
    cls = ctx.classifier.classify(a.title, body, vec)
    route, method, mv, conf = cls.route, cls.method, ctx.lexicon_mv, cls.confidence
    primary, secondary, scores = cls.primary, cls.secondary, cls.scores
    if route in ("secondary", "llm", "uncertain") and ctx.use_models and cls.scores:
        candidates = sorted(cls.scores, key=lambda k: -cls.scores[k])[:6]
        labels = {cid: ctx.classifier.nodes[cid].name_en for cid in candidates}
        try:
            best, p, zs = zero_shot_rerank(text, labels)
            if p >= get_settings().secondary_threshold:
                primary, conf, route, method, mv = (
                    best,
                    round(p, 4),
                    "secondary",
                    "zero_shot",
                    ctx.zero_shot_mv,
                )
                secondary = [c for c in candidates if c != best and zs[c] >= 0.5 * p][:3]
        except Exception as exc:
            log.info("zero_shot_unavailable", error=str(exc)[:120])
    if (
        route in ("llm", "uncertain")
        and conf < get_settings().secondary_threshold
        and ctx.llm
        and ctx.llm_budget_left > 0
    ):
        primary, secondary, conf, route, method, mv = _llm_review(ctx, a, text, primary, secondary, conf)
    if primary is not None and conf >= get_settings().secondary_threshold * 0.5:
        evidence = {"terms": cls.evidence.get(primary, [])[:8]}
        session.add(
            m.CategoryAssignment(
                article_id=a.id,
                category_id=primary,
                rank="primary",
                score=scores.get(primary, conf),
                route=route,
                evidence=evidence,
                model_version_id=mv,
                method=method,
                confidence=conf,
                analysis_version=ANALYSIS_VERSION,
            )
        )
        for sid in secondary:
            session.add(
                m.CategoryAssignment(
                    article_id=a.id,
                    category_id=sid,
                    rank="secondary",
                    score=scores.get(sid, 0.0),
                    route=route,
                    evidence={"terms": cls.evidence.get(sid, [])[:8]},
                    model_version_id=mv,
                    method=method,
                    confidence=round(conf * scores.get(sid, 0.0) / max(scores.get(primary, 1e-9), 1e-9), 4)
                    if scores.get(primary)
                    else conf,
                    analysis_version=ANALYSIS_VERSION,
                )
            )
    else:
        ctx.stats["uncertain"] += 1

    # ---- sentiment / emotion / tone (separate dimensions)
    sent = affect.analyse_sentiment(text, a.language, ctx.use_models)
    session.add(
        m.SentimentAnalysis(
            article_id=a.id,
            polarity=sent.label if sent.confidence >= 0.35 else "uncertain",
            scores=sent.scores,
            intensity=sent.intensity,
            model_version_id=ctx.sentiment_mv if sent.method != "lexicon" else ctx.lexicon_mv,
            method=sent.method,
            confidence=sent.confidence,
            analysis_version=ANALYSIS_VERSION,
        )
    )
    for kind in ("emotion", "tone"):
        res = affect.analyse_distribution(kind, text, ctx.use_models)
        session.add(
            m.EmotionAnalysis(
                article_id=a.id,
                kind=kind,
                scores=res.scores | ({"_evidence": res.evidence} if res.evidence else {}),
                dominant=res.label,
                model_version_id=ctx.zero_shot_mv if res.method.startswith("model") else ctx.lexicon_mv,
                method=res.method,
                confidence=res.confidence,
                analysis_version=ANALYSIS_VERSION,
            )
        )

    # ---- frames
    for fh in detect_frames(text, ctx.frames, ctx.use_models):
        session.add(
            m.FramingAnalysis(
                article_id=a.id,
                frame_id=fh.frame_id,
                score=fh.score,
                evidence_sentence=fh.evidence_sentence,
                method=fh.method,
                model_version_id=ctx.zero_shot_mv if "zero_shot" in fh.method else ctx.lexicon_mv,
                confidence=fh.confidence,
                analysis_version=ANALYSIS_VERSION,
            )
        )

    # ---- targeted (actor-anchored) sentiment: only where the sentence itself carries polarity
    seen: set[tuple[int, str]] = set()
    for mm in mentions:
        if mm.entity_type not in TARGET_TYPES or (mm.entity_id, mm.sentence) in seen:
            continue
        seen.add((mm.entity_id, mm.sentence))
        ss = affect.analyse_sentiment(mm.sentence, a.language, ctx.use_models)
        polar = ss.scores.get("positive", 0) - ss.scores.get("negative", 0)
        if ss.label == "neutral" or abs(polar) < 0.25 or ss.confidence < 0.45:
            continue  # do not infer unsupported sentiment
        session.add(
            m.TargetedSentiment(
                article_id=a.id,
                entity_id=mm.entity_id,
                sentiment=ss.label,
                score=round(polar, 4),
                evidence_sentence=mm.sentence[:1000],
                method=f"sentence_{ss.method}",
                model_version_id=ctx.sentiment_mv if ss.method != "lexicon" else ctx.lexicon_mv,
                confidence=ss.confidence,
                analysis_version=ANALYSIS_VERSION,
            )
        )

    # ---- events
    session.execute(delete(m.EventMention).where(m.EventMention.article_id == a.id))
    for ev in extract_events(a.title, body, mentions, ctx.location_ids):
        _store_event(session, a, ev, ctx.events_mv)


def _store_event(session: Session, a: m.Article, ev, model_version: int) -> None:
    import datetime as dt

    day = a.published_at.date()
    event = session.scalar(
        select(m.Event)
        .where(
            m.Event.event_type == ev.event_type,
            m.Event.location_entity_id == ev.location_entity_id,
            m.Event.event_date.between(day - dt.timedelta(days=1), day),
        )
        .order_by(m.Event.event_date)
    )
    if event is None:
        event = m.Event(
            event_type=ev.event_type,
            event_date=day,
            location_entity_id=ev.location_entity_id,
            title=a.title[:500],
            confidence=ev.confidence,
            method="rule",
            report_count=0,
            source_count=0,
            model_version_id=model_version,
        )
        session.add(event)
        session.flush()
    session.merge(
        m.EventMention(
            event_id=event.id,
            article_id=a.id,
            confidence=ev.confidence,
            evidence_sentence=ev.evidence_sentence[:1000],
            trigger=ev.trigger,
        )
    )
    for actor in ev.actor_entity_ids:
        existing = session.get(m.EventActor, (event.id, actor))
        if existing:
            existing.mention_count += 1
        else:
            session.add(m.EventActor(event_id=event.id, entity_id=actor, mention_count=1))
    session.flush()
    stats = session.execute(
        select(m.Article.source_id)
        .join(m.EventMention, m.EventMention.article_id == m.Article.id)
        .where(m.EventMention.event_id == event.id)
    ).all()
    event.report_count = len(stats)
    event.source_count = len({r[0] for r in stats})
    event.confidence = round(
        min(0.95, max(event.confidence, ev.confidence) + 0.03 * (event.source_count - 1)), 3
    )


def _llm_review(ctx: Context, a: m.Article, text: str, primary, secondary, conf):
    from hudhud.llm.client import verbatim_or_none

    session = ctx.session
    slugs = {n.slug: nid for nid, n in ctx.classifier.nodes.items()}
    ctx.llm_budget_left -= 1
    review = ctx.llm.call(
        "article_review",
        categories=", ".join(sorted(slugs)),
        frames=", ".join(f.slug for f in ctx.frames),
        language=a.language or "unknown",
        title=a.title,
        text=text[:4000],
    )
    if review is None:
        return primary, secondary, conf, "uncertain", "keywords", ctx.lexicon_mv
    ctx.stats["llm_reviews"] += 1
    mv = model_version_id(session, get_settings().llm_model, "article_review-1.0", provider="anthropic")
    # LLM frames are stored only with a verbatim evidence sentence
    by_slug = {f.slug: f for f in ctx.frames}
    for fr in review.frames:
        quote = verbatim_or_none(fr.evidence_quote, text)
        if fr.frame in by_slug and quote:
            session.add(
                m.FramingAnalysis(
                    article_id=a.id,
                    frame_id=by_slug[fr.frame].id,
                    score=fr.confidence,
                    evidence_sentence=quote,
                    method="llm",
                    model_version_id=mv,
                    confidence=fr.confidence,
                    analysis_version=ANALYSIS_VERSION,
                )
            )
    if review.primary_category in slugs:
        return (
            slugs[review.primary_category],
            [slugs[s] for s in review.secondary_categories if s in slugs][:3],
            round(review.confidence, 4),
            "llm",
            "llm",
            mv,
        )
    return primary, secondary, conf, "uncertain", "llm", mv
