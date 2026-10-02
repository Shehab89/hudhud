"""Daily pipeline orchestration: ingest -> dedup -> analyse -> topics -> metrics.

Each stage commits its own work, so a failure in a later stage never loses earlier
results, and every stage only picks up rows still waiting for it (``processing_status``),
so re-running the pipeline is safe. A failed stage is recorded in ``pipeline_errors``
and later stages still run on whatever data is available; the run ends as ``success``,
``partial`` (some stage or feed failed) or ``failed`` (nothing usable was produced).
"""

from __future__ import annotations

import datetime as dt
import os
import subprocess
import traceback
from collections.abc import Callable
from typing import Any

import structlog
from sqlalchemy.orm import Session

from observatory.db import models as m
from observatory.pipeline.ingest import record_error

log = structlog.get_logger()
STAGES = ("ingest", "dedup", "analyse", "topics", "metrics")


def git_sha() -> str | None:
    sha = os.environ.get("GITHUB_SHA")
    if sha:
        return sha[:40]
    try:
        return (
            subprocess.run(
                ["git", "rev-parse", "HEAD"],  # noqa: S607
                capture_output=True,
                text=True,
                timeout=5,  # noqa: S607
                check=True,
            ).stdout.strip()[:40]
            or None
        )
    except Exception:
        return None


def _stage_fn(name: str) -> Callable[[Session, int], Any]:
    if name == "ingest":
        from observatory.pipeline.ingest import run_ingest

        return lambda s, rid: run_ingest(s, rid).as_dict()
    if name == "dedup":
        from observatory.pipeline.dedup import run_dedup

        return lambda s, rid: run_dedup(s)
    if name == "analyse":
        from observatory.pipeline.analyse import run_analyse

        return lambda s, rid: run_analyse(s, rid)
    if name == "topics":
        from observatory.pipeline.topics_stage import run_topics

        return lambda s, rid: run_topics(s)
    if name == "metrics":
        from observatory.pipeline.metrics import run_metrics

        return lambda s, rid: run_metrics(s, run_id=rid)
    raise ValueError(f"unknown stage {name}")


def run_pipeline(
    session: Session, stages: tuple[str, ...] = STAGES, trigger: str = "manual", run_type: str = "daily"
) -> m.PipelineRun:
    run = m.PipelineRun(run_type=run_type, trigger=trigger, git_sha=git_sha(), status="running", stats={})
    session.add(run)
    session.commit()
    stats: dict[str, Any] = {}
    failed: list[str] = []
    for name in stages:
        started = dt.datetime.now(dt.UTC)
        log.info("stage_start", stage=name, run_id=run.id)
        try:
            result = _stage_fn(name)(session, run.id)
            session.commit()
            stats[name] = {"status": "ok", "result": result}
        except Exception as exc:  # one stage failing must not abort the rest
            session.rollback()
            failed.append(name)
            record_error(
                session,
                run.id,
                stage=name,
                error_type=type(exc).__name__,
                message=f"{exc}\n{traceback.format_exc(limit=5)}",
            )
            session.commit()
            stats[name] = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"[:500]}
            log.error("stage_failed", stage=name, error=str(exc))
        stats[name]["seconds"] = round((dt.datetime.now(dt.UTC) - started).total_seconds(), 1)

    feed_failures = (stats.get("ingest", {}).get("result") or {}).get("feeds_failed", 0)
    if len(failed) == len(stages):
        status = "failed"
    elif failed or feed_failures:
        status = "partial"
    else:
        status = "success"
    run = session.merge(run)
    run.status, run.stats, run.finished_at = status, _jsonable(stats), dt.datetime.now(dt.UTC)
    session.commit()
    log.info("pipeline_done", run_id=run.id, status=status, failed=failed)
    return run


def _jsonable(o: Any) -> Any:
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, list | tuple | set):
        return [_jsonable(v) for v in o]
    if isinstance(o, dt.date | dt.datetime):
        return o.isoformat()
    if isinstance(o, int | float | str | bool) or o is None:
        return o
    return str(o)
