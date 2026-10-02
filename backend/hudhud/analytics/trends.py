"""Trend statistics for categories and topics (from ``topic_metrics``).

frequency           articles in the recent window
growth_rate         (recent - previous) / (previous + 1), windows of equal length
acceleration        growth of the second half of the recent window minus the first half
source_diversity    Shannon entropy of outlets covering it in the recent window
language_diversity  number of languages in the recent window

Status rules (documented in the methodology): emerging when growth >= 1.0 and at
least 5 articles from 3+ outlets; declining when growth <= -0.5 and the previous
window had at least 5 articles; otherwise stable. Frequency alone never makes a
topic "important".
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from hudhud.pipeline.metrics import shannon


@dataclass
class Trend:
    ref_id: int
    frequency: int
    previous: int
    growth_rate: float
    acceleration: float
    source_count: int
    source_diversity: float | None
    language_count: int
    status: str
    series: list[tuple[str, int]]


def classify(recent: int, previous: int, growth: float, sources: int) -> str:
    if growth >= 1.0 and recent >= 5 and sources >= 3:
        return "emerging"
    if growth <= -0.5 and previous >= 5:
        return "declining"
    return "stable"


def compute_trends(
    session: Session, dimension: str, end: dt.date, window_days: int = 7, ref_ids: list[int] | None = None
) -> list[Trend]:
    start_prev = end - dt.timedelta(days=2 * window_days - 1)
    start_recent = end - dt.timedelta(days=window_days - 1)
    params = {"dim": dimension, "s": start_prev, "e": end}
    where_ref = ""
    if ref_ids:
        where_ref = " AND ref_id = ANY(:refs)"
        params["refs"] = ref_ids
    rows = session.execute(
        text(f"""SELECT ref_id, day, article_count, language_count FROM topic_metrics
        WHERE dimension = :dim AND day BETWEEN :s AND :e{where_ref} ORDER BY ref_id, day"""),
        params,
    ).all()
    src_rows = session.execute(
        text(f"""
        SELECT x.ref_id, a.source_id, count(*) FROM (
          SELECT ca.category_id ref_id, ca.article_id FROM category_assignments ca WHERE ca.is_current AND :dim='category'
          UNION ALL SELECT c.parent_id, ca.article_id FROM category_assignments ca JOIN categories c ON c.id=ca.category_id
            WHERE ca.is_current AND c.parent_id IS NOT NULL AND :dim='category'
          UNION ALL SELECT ta.topic_id, ta.article_id FROM topic_assignments ta
            JOIN topic_models tm ON tm.id=ta.topic_model_id AND tm.status='active' WHERE :dim='topic') x
        JOIN articles a ON a.id = x.article_id
        WHERE a.duplicate_of_id IS NULL AND a.published_at::date BETWEEN :r AND :e{where_ref.replace("ref_id", "x.ref_id")}
        GROUP BY 1, 2"""),
        params | {"r": start_recent},
    ).all()
    sources: dict[int, list[int]] = {}
    for ref, _sid, cnt in src_rows:
        sources.setdefault(ref, []).append(cnt)

    by_ref: dict[int, dict[dt.date, tuple[int, int]]] = {}
    for ref, day, cnt, lc in rows:
        by_ref.setdefault(ref, {})[day] = (cnt, lc)
    out = []
    half = window_days // 2
    for ref, days in by_ref.items():
        series = []
        for i in range(2 * window_days):
            d = start_prev + dt.timedelta(days=i)
            series.append((d.isoformat(), days.get(d, (0, 0))[0]))
        prev = sum(c for _, c in series[:window_days])
        recent_series = [c for _, c in series[window_days:]]
        recent = sum(recent_series)
        growth = round((recent - prev) / (prev + 1.0), 4)
        first, second = sum(recent_series[:half]), sum(recent_series[half:])
        accel = round((second - first) / (first + 1.0), 4)
        langs = max((v[1] for d, v in days.items() if d >= start_recent), default=0)
        src = sources.get(ref, [])
        out.append(
            Trend(
                ref,
                recent,
                prev,
                growth,
                accel,
                len(src),
                shannon(src),
                langs,
                classify(recent, prev, growth, len(src)),
                series[window_days:],
            )
        )
    return sorted(out, key=lambda t: -t.frequency)
