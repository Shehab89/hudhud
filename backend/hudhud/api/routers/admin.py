"""Operational endpoints. All require the X-Admin-Token header (ADMIN_TOKEN)."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from hudhud.api.deps import DB, Admin, Page
from hudhud.db import models as m
from hudhud.review.corrections import CorrectionError, apply_correction

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Admin])


@router.get("/runs", summary="Pipeline runs, newest first")
def runs(db: DB, page: Page) -> list[dict]:
    limit, offset = page
    out = []
    for r in db.scalars(
        select(m.PipelineRun).order_by(m.PipelineRun.started_at.desc()).limit(limit).offset(offset)
    ):
        errors = db.scalar(select(func.count()).where(m.PipelineError.run_id == r.id))
        out.append(
            {
                "id": r.id,
                "type": r.run_type,
                "trigger": r.trigger,
                "git_sha": r.git_sha,
                "status": r.status,
                "started_at": r.started_at,
                "finished_at": r.finished_at,
                "errors": errors,
                "stats": r.stats,
            }
        )
    return out


@router.get("/errors", summary="Pipeline errors")
def errors(
    db: DB, page: Page, run_id: int | None = None, stage: Annotated[str | None, Query()] = None
) -> list[dict]:
    q = select(m.PipelineError, m.Source.slug).outerjoin(m.Source, m.Source.id == m.PipelineError.source_id)
    if run_id:
        q = q.where(m.PipelineError.run_id == run_id)
    if stage:
        q = q.where(m.PipelineError.stage == stage)
    limit, offset = page
    return [
        {
            "id": e.id,
            "run_id": e.run_id,
            "source": slug,
            "feed_id": e.feed_id,
            "article_id": e.article_id,
            "stage": e.stage,
            "error_type": e.error_type,
            "message": e.message[:1000],
            "retry_count": e.retry_count,
            "status": e.status,
            "created_at": e.created_at,
        }
        for e, slug in db.execute(q.order_by(m.PipelineError.id.desc()).limit(limit).offset(offset)).all()
    ]


@router.get("/annotations", summary="Submitted corrections awaiting review")
def annotations(
    db: DB, page: Page, status: Literal["submitted", "accepted", "rejected"] = "submitted"
) -> list[dict]:
    limit, offset = page
    return [
        {
            "id": a.id,
            "user_id": a.user_id,
            "article_id": a.article_id,
            "source_id": a.source_id,
            "target_type": a.target_type,
            "target_id": a.target_id,
            "original_value": a.original_value,
            "corrected_value": a.corrected_value,
            "note": a.note,
            "status": a.status,
            "created_at": a.created_at,
        }
        for a in db.scalars(
            select(m.Annotation)
            .where(m.Annotation.status == status)
            .order_by(m.Annotation.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ]


class Review(BaseModel):
    status: Literal["accepted", "rejected"]


@router.patch("/annotations/{annotation_id}", summary="Accept (and apply) or reject a correction")
def review(db: DB, annotation_id: int, body: Review) -> dict:
    a = db.get(m.Annotation, annotation_id)
    if a is None:
        raise HTTPException(404, "annotation not found")
    if a.status != "submitted":
        raise HTTPException(409, f"annotation already {a.status}")
    applied = False
    if body.status == "accepted":
        try:
            applied = apply_correction(db, a)
        except CorrectionError as exc:
            db.rollback()
            raise HTTPException(422, str(exc)) from exc
    a.status = body.status
    db.commit()
    return {"id": a.id, "status": a.status, "applied": applied}


@router.get("/llm-calls", summary="Recent LLM calls with cost and validity")
def llm_calls(db: DB, page: Page) -> list[dict]:
    limit, offset = page
    return [
        {
            "id": c.id,
            "model": c.model,
            "valid": c.valid,
            "attempts": c.attempts,
            "input_tokens": c.input_tokens,
            "output_tokens": c.output_tokens,
            "cost_usd": c.cost_usd,
            "error": c.error,
            "created_at": c.created_at,
        }
        for c in db.scalars(select(m.LLMCall).order_by(m.LLMCall.id.desc()).limit(limit).offset(offset))
    ]
