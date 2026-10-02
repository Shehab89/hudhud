"""Shared fixtures.

Unit tests need nothing. Tests marked ``db`` need a disposable PostgreSQL database with
the pgvector extension available, given as ``TEST_DATABASE_URL``; they are skipped when
it is unset. The test database is wiped and rebuilt from the migrations: never point
``TEST_DATABASE_URL`` at a database you care about.
"""

from __future__ import annotations

import os

# Configure before anything imports hudhud.config (settings are cached).
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")
if TEST_DATABASE_URL:
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("NLP_BACKEND", "fallback")  # deterministic, no model downloads
os.environ["LLM_PROVIDER"] = "none"
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["ADMIN_TOKEN"] = "test-admin-token"
os.environ["API_RATE_LIMIT"] = "100000/minute"
os.environ["FETCH_BACKOFF_BASE_SECONDS"] = "0"

from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402

BACKEND = Path(__file__).resolve().parents[1]

# Tables filled by the pipeline or by users; everything else is registry/seed data.
DATA_TABLES = (
    "articles",
    "article_story_clusters",
    "pipeline_runs",
    "pipeline_errors",
    "llm_calls",
    "topic_models",
    "global_topics",
    "events",
    "claims",
    "terminology_variants",
    "daily_metrics",
    "topic_metrics",
    "source_metrics",
    "entity_metrics",
    "daily_summaries",
    "drift_reports",
    "users",
    "saved_queries",
    "annotations",
)


@pytest.fixture(scope="session")
def db_url() -> str:
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL is not set")
    from alembic.config import Config
    from sqlalchemy import create_engine

    from alembic import command

    engine = create_engine(TEST_DATABASE_URL)
    with engine.begin() as c:
        c.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        c.execute(text("CREATE SCHEMA public"))
    engine.dispose()
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL.replace("%", "%%"))
    command.upgrade(cfg, "head")

    from hudhud.db.session import session_scope
    from hudhud.registry.seed import seed_all

    with session_scope() as s:
        seed_all(s)
    return TEST_DATABASE_URL


def wipe_data(session) -> None:
    session.execute(text(f"TRUNCATE {', '.join(DATA_TABLES)} RESTART IDENTITY CASCADE"))
    session.execute(
        text("DELETE FROM source_languages WHERE source_id IN (SELECT id FROM sources WHERE is_demo)")
    )
    session.execute(text("DELETE FROM sources WHERE is_demo OR slug LIKE 'test-%'"))
    session.commit()


@pytest.fixture
def session(db_url):
    from hudhud.db.session import session_factory

    s = session_factory()()
    wipe_data(s)
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture(scope="module")
def demo_db(db_url):
    """A database holding a small DEMO DATA corpus that has been through the whole pipeline."""
    from hudhud import demo
    from hudhud.db.session import session_factory
    from hudhud.pipeline.run import run_pipeline

    s = session_factory()()
    wipe_data(s)
    demo.generate(s, days=14, stories_per_day=6)
    s.commit()
    run = run_pipeline(s, ("dedup", "analyse", "topics", "metrics"), trigger="test", run_type="partial")
    s.info["run"] = {"id": run.id, "status": run.status, "stats": run.stats}
    try:
        yield s
    finally:
        s.rollback()
        s.close()
