import pytest
from sqlalchemy import func, select

from observatory.db import models as m
from observatory.pipeline.run import run_pipeline

pytestmark = pytest.mark.db


def test_demo_pipeline_succeeds(demo_db):
    run = demo_db.info["run"]
    assert run["status"] == "success", run["stats"]
    assert run["stats"]["dedup"]["result"]["new"] > 0
    analysed = demo_db.scalar(select(func.count(m.SentimentAnalysis.id)))
    assert analysed > 0


def test_every_article_is_demo_labelled(demo_db):
    assert demo_db.scalar(select(func.count(m.Article.id)).where(m.Article.is_demo.is_(False))) == 0
    urls = demo_db.scalars(select(m.Article.url)).all()
    assert all(".demo.invalid" in u for u in urls)


def test_concepts_stay_separate(demo_db):
    """Sentiment, framing and orientation are stored independently, each with provenance."""
    s = demo_db.scalar(select(m.SentimentAnalysis).limit(1))
    assert s.polarity in {"negative", "neutral", "positive", "uncertain"}
    assert s.model_version_id is not None and s.confidence is not None
    f = demo_db.scalar(select(m.FramingAnalysis).limit(1))
    assert f is not None and f.frame_id is not None


def test_rerun_is_idempotent(demo_db):
    before = demo_db.scalar(select(func.count(m.SentimentAnalysis.id)))
    run = run_pipeline(demo_db, ("dedup", "analyse", "metrics"), trigger="test", run_type="partial")
    assert run.status == "success"
    assert run.stats["dedup"]["result"] == {"new": 0}
    assert demo_db.scalar(select(func.count(m.SentimentAnalysis.id))) == before
