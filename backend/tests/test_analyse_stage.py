"""The analyse stage with stand-in transformer models, so the real columns are exercised.

A model-backed run on GitHub once failed for every article because the model's name was
stored in a 40-character column; the fallback backend used by the other tests never hit it.
"""

import pytest
from sqlalchemy import func, select

from hudhud import demo
from hudhud.config import get_settings
from hudhud.db import models as m
from hudhud.nlp import affect
from hudhud.nlp import classify as classify_mod
from hudhud.pipeline import analyse as analyse_mod
from hudhud.pipeline.run import run_pipeline

pytestmark = pytest.mark.db


class FakeZeroShot:
    def __call__(self, text, candidate_labels, multi_label=False, hypothesis_template=""):
        labels = list(candidate_labels)
        return {"labels": labels, "scores": [1.0 / (i + 2) for i in range(len(labels))]}


def fake_sentiment_pipe(model):
    def run(text):
        return [
            [
                {"label": "negative", "score": 0.6},
                {"label": "neutral", "score": 0.3},
                {"label": "positive", "score": 0.1},
            ]
        ]

    return run


@pytest.fixture
def deduped(session):
    demo.generate(session, days=4, stories_per_day=4)
    session.commit()
    run_pipeline(session, ("dedup",), trigger="test", run_type="partial")
    return session


def test_model_results_fit_the_columns_and_name_their_model(deduped, monkeypatch):
    session = deduped
    monkeypatch.setattr(affect, "_sentiment_pipe", fake_sentiment_pipe)
    monkeypatch.setattr(classify_mod, "_zero_shot_pipeline", lambda: FakeZeroShot())
    monkeypatch.setattr(get_settings(), "zero_shot_affect", True)
    ctx = analyse_mod.build_context(session)
    ctx.use_models = True
    ctx.zero_shot_mv = ctx.model_mv(get_settings().zero_shot_model)
    arts = session.scalars(
        select(m.Article).where(m.Article.processing_status == "deduped", m.Article.duplicate_of_id.is_(None))
    ).all()
    assert arts
    todo = analyse_mod._embed_batch(ctx, arts)
    analyse_mod._analyse_batch(ctx, todo, None)
    session.commit()

    assert session.scalar(select(func.count(m.PipelineError.id))) == 0
    assert all(a.processing_status == "analysed" for a in todo)
    methods = set(session.scalars(select(m.SentimentAnalysis.method))) | set(
        session.scalars(select(m.EmotionAnalysis.method))
    )
    assert methods == {"model"}

    s = get_settings()
    names = {
        lang: set(
            session.scalars(
                select(m.Model.name)
                .join(m.ModelVersion, m.ModelVersion.model_id == m.Model.id)
                .join(m.SentimentAnalysis, m.SentimentAnalysis.model_version_id == m.ModelVersion.id)
                .join(m.Article, m.Article.id == m.SentimentAnalysis.article_id)
                .where(m.Article.language == lang)
            )
        )
        for lang in ("ar", "en")
    }
    assert names["ar"] == {s.sentiment_model_ar}  # Arabic is read by the Arabic model, and says so
    assert names["en"] == {s.sentiment_model}
    emotion_models = set(
        session.scalars(
            select(m.Model.name)
            .join(m.ModelVersion, m.ModelVersion.model_id == m.Model.id)
            .join(m.EmotionAnalysis, m.EmotionAnalysis.model_version_id == m.ModelVersion.id)
        )
    )
    assert emotion_models == {s.zero_shot_model}


def test_time_budget_defers_articles_and_the_next_run_finishes_them(deduped, monkeypatch):
    session = deduped
    regrouped = []
    real = analyse_mod.rebuild_story_clusters
    monkeypatch.setattr(
        analyse_mod, "rebuild_story_clusters", lambda s, start: regrouped.append(start) or real(s, start)
    )
    waiting = session.scalar(
        select(func.count(m.Article.id)).where(
            m.Article.processing_status == "deduped", m.Article.duplicate_of_id.is_(None)
        )
    )
    assert waiting > 0

    first = analyse_mod.run_analyse(session, None, max_seconds=1e-9)
    assert first["deferred"] == waiting and first["analysed"] == 0
    # every article was still embedded and the stories regrouped, so matching does not wait
    assert session.scalar(select(func.count(m.ArticleEmbedding.article_id))) >= waiting
    assert len(regrouped) == 1
    assert session.scalar(select(func.count(m.SentimentAnalysis.id))) == 0
    assert (
        session.scalar(select(func.count(m.Article.id)).where(m.Article.processing_status == "deduped"))
        >= waiting
    )

    second = analyse_mod.run_analyse(session, None)
    assert second["deferred"] == 0 and second["analysed"] == waiting
    assert second["embedded"] == 0  # embeddings were cached by the first run
    assert session.scalar(select(func.count(m.SentimentAnalysis.id))) == waiting


def test_emotion_and_tone_use_the_lexicon_unless_zero_shot_is_switched_on(deduped, monkeypatch):
    session = deduped
    monkeypatch.setattr(affect, "_sentiment_pipe", fake_sentiment_pipe)
    monkeypatch.setattr(classify_mod, "_zero_shot_pipeline", lambda: FakeZeroShot())
    assert get_settings().zero_shot_affect is False
    ctx = analyse_mod.build_context(session)
    ctx.use_models = True
    ctx.zero_shot_mv = ctx.model_mv(get_settings().zero_shot_model)
    arts = session.scalars(
        select(m.Article).where(m.Article.processing_status == "deduped", m.Article.duplicate_of_id.is_(None))
    ).all()
    analyse_mod._analyse_batch(ctx, analyse_mod._embed_batch(ctx, arts), None)
    session.commit()
    assert set(session.scalars(select(m.EmotionAnalysis.method))) == {"lexicon"}
    assert set(session.scalars(select(m.SentimentAnalysis.method))) == {
        "model"
    }  # sentiment still uses models
