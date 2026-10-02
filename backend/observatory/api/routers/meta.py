"""Vocabularies, the model registry and the public data-quality dashboard."""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter
from sqlalchemy import func, select, text

from observatory.api.deps import DB
from observatory.config import get_settings
from observatory.db import models as m
from observatory.nlp.events import EVENT_TRIGGERS
from observatory.nlp.registry import ANALYSIS_VERSION

router = APIRouter(tags=["meta"])

OPERATING_BASES = ["sanaa_controlled", "government_controlled", "stc_controlled", "outside_yemen", "unknown"]


@router.get("/meta", summary="Controlled vocabularies and configuration the frontend needs")
def meta(db: DB) -> dict:
    s = get_settings()
    return {
        "analysis_version": ANALYSIS_VERSION,
        "languages": [
            {"code": lang.code, "name": lang.name_en, "name_native": lang.name_native, "rtl": lang.rtl}
            for lang in db.scalars(select(m.Language).order_by(m.Language.code))
        ],
        "source_groups": list(
            db.scalars(select(m.Source.source_group).distinct().order_by(m.Source.source_group))
        ),
        "operating_bases": OPERATING_BASES,
        "frames": [
            {"slug": f.slug, "name_en": f.name_en, "name_ar": f.name_ar, "description": f.description}
            for f in db.scalars(select(m.Frame).order_by(m.Frame.name_en))
        ],
        "event_types": sorted(EVENT_TRIGGERS),
        "entity_types": list(
            db.scalars(select(m.Entity.entity_type).distinct().order_by(m.Entity.entity_type))
        ),
        "routing_thresholds": {"accept": s.accept_threshold, "secondary_model": s.secondary_threshold},
        "llm_enabled": s.llm_provider == "anthropic" and bool(s.anthropic_api_key),
        "has_demo_data": bool(
            db.scalar(select(func.count()).select_from(m.Article).where(m.Article.is_demo.is_(True)))
        ),
        "data_range": dict(
            zip(
                ("first", "last"),
                db.execute(select(func.min(m.Article.published_at), func.max(m.Article.published_at))).one(),
                strict=True,
            )
        ),
    }


@router.get("/models", summary="Model registry: every model and version that produced a stored result")
def models(db: DB) -> dict:
    out = []
    for mod in db.scalars(select(m.Model).order_by(m.Model.name)):
        tasks = list(db.scalars(select(m.ModelTask.task).where(m.ModelTask.model_id == mod.id)))
        langs = list(
            db.scalars(select(m.ModelLanguage.language_code).where(m.ModelLanguage.model_id == mod.id))
        )
        versions = []
        for v in db.scalars(select(m.ModelVersion).where(m.ModelVersion.model_id == mod.id)):
            bench = [
                {
                    "task": b.task,
                    "dataset": b.dataset,
                    "language": b.language,
                    "metric": b.metric,
                    "value": b.value,
                    "n": b.n,
                    "notes": b.notes,
                }
                for b in db.scalars(select(m.ModelBenchmark).where(m.ModelBenchmark.model_version_id == v.id))
            ]
            versions.append(
                {
                    "version": v.version,
                    "parameters": v.parameters,
                    "created_at": v.created_at,
                    "benchmarks": bench,
                }
            )
        out.append(
            {
                "name": mod.name,
                "provider": mod.provider,
                "license": mod.license,
                "url": mod.url,
                "description": mod.description,
                "tasks": tasks,
                "languages": langs,
                "versions": versions,
                "in_use": bool(versions),
            }
        )
    prompts = [
        {
            "name": p.name,
            "version": p.version,
            "model": p.model,
            "temperature": p.temperature,
            "created_at": p.created_at,
        }
        for p in db.scalars(select(m.PromptTemplate).order_by(m.PromptTemplate.name))
    ]
    since = dt.datetime.now(dt.UTC) - dt.timedelta(days=30)
    llm = db.execute(
        select(
            func.count(),
            func.coalesce(func.sum(m.LLMCall.cost_usd), 0),
            func.count().filter(m.LLMCall.valid.is_(False)),
        ).where(m.LLMCall.created_at >= since)
    ).one()
    return {
        "analysis_version": ANALYSIS_VERSION,
        "models": out,
        "prompts": prompts,
        "llm_last_30_days": {"calls": llm[0], "cost_usd": round(float(llm[1]), 4), "failed": llm[2]},
    }


@router.get("/quality", summary="Data-quality dashboard: source health, coverage, uncertainty and drift")
def quality(db: DB) -> dict:
    health = dict(
        db.execute(
            select(m.Source.health_status, func.count())
            .where(m.Source.active.is_(True))
            .group_by(m.Source.health_status)
        ).all()
    )
    failing = db.execute(
        select(
            m.Source.slug,
            m.Source.name,
            m.SourceFeed.feed_type,
            m.SourceFeed.health_status,
            m.SourceFeed.consecutive_failures,
            m.SourceFeed.last_success_at,
        )
        .join(m.SourceFeed, m.SourceFeed.source_id == m.Source.id)
        .where(m.SourceFeed.active.is_(True), m.SourceFeed.health_status.in_(["degraded", "failed"]))
        .order_by(m.SourceFeed.consecutive_failures.desc())
        .limit(50)
    ).all()
    daily = db.execute(
        select(
            m.DailyMetric.day,
            m.DailyMetric.articles,
            m.DailyMetric.unique_stories,
            m.DailyMetric.sources_active,
            m.DailyMetric.duplicate_rate,
            m.DailyMetric.language_distribution,
        )
        .order_by(m.DailyMetric.day.desc())
        .limit(30)
    ).all()
    since = dt.datetime.now(dt.UTC) - dt.timedelta(days=30)
    rates = db.execute(
        text("""
        SELECT count(*) FILTER (WHERE a.language IS NULL OR a.language = 'unknown')::float / nullif(count(*), 0),
               count(*) FILTER (WHERE a.is_mixed_language)::float / nullif(count(*), 0),
               count(*) FILTER (WHERE a.published_at_estimated)::float / nullif(count(*), 0),
               count(*) FILTER (WHERE a.duplicate_of_id IS NOT NULL)::float / nullif(count(*), 0),
               count(*) FILTER (WHERE a.is_syndicated)::float / nullif(count(*), 0),
               count(*) FILTER (WHERE a.processing_status = 'error')
        FROM articles a WHERE a.created_at >= :since AND a.deleted_at IS NULL"""),
        {"since": since},
    ).one()
    uncertain_sent = db.scalar(
        text("""SELECT count(*) FILTER (WHERE polarity = 'uncertain')::float / nullif(count(*), 0)
        FROM sentiment_analysis WHERE is_current AND created_at >= :since"""),
        {"since": since},
    )
    routes = dict(
        db.execute(
            text("""SELECT coalesce(route, 'n/a'), count(*) FROM category_assignments
        WHERE is_current AND rank = 'primary' AND created_at >= :since GROUP BY 1"""),
            {"since": since},
        ).all()
    )
    methods = dict(
        db.execute(
            text("""SELECT method, count(*) FROM sentiment_analysis
        WHERE is_current AND created_at >= :since GROUP BY 1"""),
            {"since": since},
        ).all()
    )
    runs = db.execute(
        select(
            m.PipelineRun.id,
            m.PipelineRun.run_type,
            m.PipelineRun.status,
            m.PipelineRun.started_at,
            m.PipelineRun.finished_at,
        )
        .order_by(m.PipelineRun.started_at.desc())
        .limit(14)
    ).all()
    drift = db.execute(
        select(
            m.DriftReport.day,
            m.DriftReport.metric,
            m.DriftReport.value,
            m.DriftReport.threshold,
            m.DriftReport.flagged,
        )
        .order_by(m.DriftReport.day.desc(), m.DriftReport.metric)
        .limit(40)
    ).all()
    gaps = db.execute(
        text("""SELECT s.slug, s.name, max(a.published_at) FROM sources s
        LEFT JOIN articles a ON a.source_id = s.id WHERE s.active AND NOT s.is_demo GROUP BY s.id
        HAVING max(a.published_at) IS NULL OR max(a.published_at) < now() - interval '7 days'
        ORDER BY 3 NULLS FIRST LIMIT 50""")
    ).all()
    rate = lambda v: round(float(v), 4) if v is not None else None  # noqa: E731
    return {
        "source_health": health,
        "failing_feeds": [
            {
                "source": r[0],
                "name": r[1],
                "feed_type": r[2],
                "health": r[3],
                "consecutive_failures": r[4],
                "last_success_at": r[5],
            }
            for r in failing
        ],
        "sources_silent_7_days": [{"source": r[0], "name": r[1], "last_article_at": r[2]} for r in gaps],
        "daily": [
            {
                "day": r[0],
                "articles": r[1],
                "unique_stories": r[2],
                "sources_active": r[3],
                "duplicate_rate": r[4],
                "languages": r[5],
            }
            for r in daily
        ],
        "last_30_days": {
            "unknown_language_rate": rate(rates[0]),
            "mixed_language_rate": rate(rates[1]),
            "estimated_date_rate": rate(rates[2]),
            "duplicate_rate": rate(rates[3]),
            "syndicated_rate": rate(rates[4]),
            "processing_errors": rates[5],
            "uncertain_sentiment_rate": rate(uncertain_sent),
            "category_routes": routes,
            "sentiment_methods": methods,
        },
        "pipeline_runs": [
            {"id": r[0], "type": r[1], "status": r[2], "started_at": r[3], "finished_at": r[4]} for r in runs
        ],
        "drift": [
            {"day": r[0], "metric": r[1], "value": r[2], "threshold": r[3], "flagged": r[4]} for r in drift
        ],
    }
