"""Applying accepted human corrections.

An accepted correction becomes a new current result with ``method="human"`` and
confidence 1.0; the model's result is kept with ``is_current=False`` so the change is
auditable and the model output can still be compared against human judgement.

Applied automatically: ``sentiment`` ({"polarity": ...}), ``category``
({"slug": ...}, replaces the primary category) and ``frame`` ({"slug": ..., "present":
true|false}). Every other correction type is stored and exported for retraining and
evaluation but is not written back into results.
"""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from observatory.db import models as m

APPLIED_TYPES = ("sentiment", "category", "frame")
POLARITIES = ("positive", "neutral", "negative", "uncertain")


class CorrectionError(ValueError):
    pass


def apply_correction(session: Session, a: m.Annotation) -> bool:
    """Write an accepted correction back into the results. Returns False when the type is not applied."""
    if a.target_type not in APPLIED_TYPES:
        return False
    if a.article_id is None:
        raise CorrectionError("article_id is required for this correction type")
    v = a.corrected_value or {}
    evidence = {"annotation_id": a.id, "note": a.note}

    if a.target_type == "sentiment":
        polarity = v.get("polarity")
        if polarity not in POLARITIES:
            raise CorrectionError(f"polarity must be one of {', '.join(POLARITIES)}")
        session.execute(
            update(m.SentimentAnalysis)
            .where(m.SentimentAnalysis.article_id == a.article_id, m.SentimentAnalysis.is_current.is_(True))
            .values(is_current=False)
        )
        session.add(
            m.SentimentAnalysis(
                article_id=a.article_id,
                polarity=polarity,
                scores={polarity: 1.0},
                method="human",
                confidence=1.0,
            )
        )
        return True

    if a.target_type == "category":
        cat = session.scalar(select(m.Category).where(m.Category.slug == v.get("slug")))
        if cat is None:
            raise CorrectionError("unknown category slug")
        session.execute(
            update(m.CategoryAssignment)
            .where(
                m.CategoryAssignment.article_id == a.article_id,
                m.CategoryAssignment.rank == "primary",
                m.CategoryAssignment.is_current.is_(True),
            )
            .values(is_current=False)
        )
        session.add(
            m.CategoryAssignment(
                article_id=a.article_id,
                category_id=cat.id,
                rank="primary",
                score=1.0,
                route="human",
                evidence=evidence,
                method="human",
                confidence=1.0,
            )
        )
        return True

    frame = session.scalar(select(m.Frame).where(m.Frame.slug == v.get("slug")))
    if frame is None:
        raise CorrectionError("unknown frame slug")
    session.execute(
        update(m.FramingAnalysis)
        .where(
            m.FramingAnalysis.article_id == a.article_id,
            m.FramingAnalysis.frame_id == frame.id,
            m.FramingAnalysis.is_current.is_(True),
        )
        .values(is_current=False)
    )
    if v.get("present", True):
        session.add(
            m.FramingAnalysis(
                article_id=a.article_id,
                frame_id=frame.id,
                score=1.0,
                evidence_sentence=v.get("evidence_sentence"),
                method="human",
                confidence=1.0,
            )
        )
    return True
