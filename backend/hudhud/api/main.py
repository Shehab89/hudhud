"""FastAPI application."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from sqlalchemy import text

from hudhud import __version__
from hudhud.api.routers import (
    actors,
    admin,
    articles,
    events,
    landscape,
    meta,
    overview,
    research,
    sources,
    taxonomy,
    topics,
)
from hudhud.config import get_settings
from hudhud.db.session import get_engine
from hudhud.logging import configure_logging

DESCRIPTION = """
Open research API for monitoring how media cover Yemen.

The platform keeps five things separate and never combines them into a single "bias" score:
**source orientation** (who the outlet is, with evidence), **article sentiment** (tone of the text),
**framing** (how an issue is presented, with evidence sentences), **topic** (what it is about) and
**actor-targeted sentiment** (how a sentence speaks about a named actor).

Every analytical result carries its method, model version and confidence. Records flagged
`is_demo: true` are synthetic **DEMO DATA** and are not real news.
"""

TAGS = [
    {"name": "overview", "description": "Headline indicators, timelines and the daily summary."},
    {"name": "articles", "description": "Article metadata, per-article analysis and hybrid search."},
    {"name": "taxonomy", "description": "Curated categories and trend statistics."},
    {"name": "topics", "description": "Data-driven topic models (BERTopic / k-means + c-TF-IDF)."},
    {"name": "sources", "description": "Source registry, orientation evidence and source comparison."},
    {"name": "actors", "description": "Actors, aliases, terminology and actor-targeted sentiment."},
    {"name": "events", "description": "Events extracted from coverage, and geography."},
    {"name": "landscape", "description": "Media ecosystem graph and narrative comparison."},
    {"name": "research", "description": "Exports, saved queries and annotations."},
    {"name": "meta", "description": "Vocabularies, model registry and data quality."},
    {"name": "admin", "description": "Pipeline operations (requires X-Admin-Token)."},
]


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()
    limiter = Limiter(key_func=get_remote_address, default_limits=[settings.api_rate_limit])
    app = FastAPI(
        title="Hudhud API",
        version=__version__,
        description=DESCRIPTION,
        openapi_tags=TAGS,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-API-Key", "X-Admin-Token"],
        allow_credentials=False,
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), camera=(), microphone=()")
        if not request.url.path.startswith(("/docs", "/redoc")):
            response.headers.setdefault(
                "Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"
            )
        if (
            request.method == "GET"
            and request.url.path.startswith("/api/")
            and "/admin/" not in request.url.path
        ):
            response.headers.setdefault("Cache-Control", "public, max-age=300")
        return response

    @app.get("/health", tags=["meta"], summary="Liveness and database check")
    def health() -> dict:
        try:
            with get_engine().connect() as c:
                c.execute(text("SELECT 1"))
            db = "ok"
        except Exception:
            db = "unavailable"
        return {"status": "ok" if db == "ok" else "degraded", "database": db, "version": __version__}

    for r in (
        overview,
        articles,
        taxonomy,
        topics,
        sources,
        actors,
        events,
        landscape,
        research,
        meta,
        admin,
    ):
        app.include_router(r.router, prefix="/api/v1")
    return app


app = create_app()
