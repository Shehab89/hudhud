"""Curated registry rules: categories, tiers, alignment vocabularies and the influence rubric.

See database/seeds/sources/SCHEMA.md. Two ideas are kept apart on purpose:

* influence (audience and weight in Yemen discourse) is computed from evidence here;
* institutional importance (speaking for an institution) is a separate, recorded attribute.

Being official raises neither the influence score nor reliability. Reliability is not
assessed (NULL) unless a record cites evidence for it.
"""

from __future__ import annotations

import math
from typing import Any

CATEGORIES = {
    "MEDIA",
    "POLITICAL_ORGANIZATION",
    "SOCIAL_ACCOUNT",
    "OFFICIAL_GOVERNMENT",
    "DIPLOMATIC_MISSION",
    "INTERNATIONAL_INSTITUTION",
    "THINK_TANK",
    "RESEARCH_ORGANIZATION",
}
DEFAULT_CONTENT_TYPE = {
    "MEDIA": "journalism",
    "POLITICAL_ORGANIZATION": "political_statement",
    "SOCIAL_ACCOUNT": "social_post",
    "OFFICIAL_GOVERNMENT": "official_statement",
    "DIPLOMATIC_MISSION": "official_statement",
    "INTERNATIONAL_INSTITUTION": "institutional_publication",
    "THINK_TANK": "analysis",
    "RESEARCH_ORGANIZATION": "analysis",
}
CONTENT_TYPES = set(DEFAULT_CONTENT_TYPE.values())
OFFICIAL_CATEGORIES = {"OFFICIAL_GOVERNMENT", "DIPLOMATIC_MISSION"}
TIERS = {"A", "B"}
REGIONS = {
    "yemen",
    "gulf",
    "iraq",
    "levant",
    "egypt",
    "maghreb",
    "iran",
    "turkey",
    "europe",
    "north_america",
    "russia",
    "asia",
    "africa",
    "global",
}
PLATFORMS = {"website", "x", "telegram", "youtube", "facebook", "instagram", "tiktok", "tv", "radio", "wire"}
YEMEN_ALIGNMENTS = {
    "plc_government",
    "ansar_allah",
    "stc",
    "islah",
    "gpc_sanaa",
    "gpc_plc",
    "national_resistance",
    "hadramawt",
    "southern_other",
    "independent",
    "mixed",
    "none_documented",
    "not_applicable",
    "unknown",
}
REGIONAL_ALIGNMENTS = {
    "saudi",
    "uae",
    "qatar",
    "oman",
    "kuwait",
    "iran_axis",
    "turkey",
    "egypt",
    "us",
    "uk",
    "eu",
    "russia",
    "china",
    "none_documented",
    "not_applicable",
    "unknown",
}
# Values that are not a claim about anyone and so need no evidence URL.
NO_CLAIM = {"unknown", "not_applicable", "none_documented"}
LEVELS = {"high", "medium", "low"}
INSTITUTIONAL_LEVELS = LEVELS | {"none"}
AUDIENCE_METRICS = {
    "x_followers",
    "youtube_subscribers",
    "facebook_followers",
    "telegram_subscribers",
    "instagram_followers",
    "tiktok_followers",
    "monthly_visits",
    "tv_reach",
    "print_circulation",
}
REVIEW_STATUSES = {"draft", "reviewed", "disputed"}

# Influence rubric v1 (documented in SCHEMA.md and docs/methodology.md).
RUBRIC_VERSION = "influence-v1"
FREQUENCY_POINTS = {"daily": 25, "weekly": 15, "monthly": 8, "occasional": 0}
REGIONAL_POINTS = {"high": 15, "medium": 8, "low": 0}
CITED_POINTS = {"high": 10, "medium": 5, "low": 0}
HISTORICAL_POINTS = {"high": 10, "medium": 5, "low": 0}
REACH_MAX = 40


def reach_points(value: float) -> float:
    """1k audience = 0, 10k = 10, 100k = 20, 1M = 30, 10M or more = 40."""
    if value <= 0:
        return 0.0
    return max(0.0, min(float(REACH_MAX), (math.log10(value) - 3) * 10))


def _number(v: Any) -> float | None:
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


# For tier B (institutional) sources these two ratings tend to restate the institution's
# rank, which is recorded separately as institutional importance. They are kept in the
# selection record but not scored, so official status cannot raise influence.
INSTITUTIONAL_HALO = ("regional_importance", "historical_importance")


def influence(selection: dict[str, Any] | None, tier: str | None = "A") -> tuple[float | None, dict[str, Any]]:
    """Score 0-100 from the evidence in a selection record, with its components.

    Influence is first of all reach, so there is no score without a citable audience figure,
    and none from fewer than two indicators: a score built on one indicator would look
    more precise than the evidence is.
    """
    sel = selection or {}
    parts: dict[str, Any] = {"rubric": RUBRIC_VERSION}
    audience = [
        a for a in sel.get("audience_evidence") or [] if _number(a.get("value")) and a.get("source_url")
    ]
    if audience:
        best = max(audience, key=lambda a: _number(a["value"]) or 0)
        parts["reach"] = round(reach_points(_number(best["value"]) or 0), 1)
        parts["reach_basis"] = {"metric": best.get("metric"), "value": _number(best["value"])}
    freq = ((sel.get("yemen_coverage") or {}).get("frequency") or "").lower()
    if freq in FREQUENCY_POINTS:
        parts["yemen_coverage"] = FREQUENCY_POINTS[freq]
    inf = sel.get("influence_evidence") or {}
    for key, table in (
        ("regional_importance", REGIONAL_POINTS),
        ("cited_by_other_media", CITED_POINTS),
        ("historical_importance", HISTORICAL_POINTS),
    ):
        level = (inf.get(key) or "").lower()
        if level not in table:
            continue
        if tier == "B" and key in INSTITUTIONAL_HALO:
            parts.setdefault("not_scored", []).append(key)
            continue
        parts[key] = table[level]
    indicators = [k for k in parts if k not in ("rubric", "reach_basis", "not_scored")]
    parts["indicators"] = len(indicators)
    if "reach" not in parts:
        parts["reason"] = "no citable audience figure"
        return None, parts
    if len(indicators) < 2:
        parts["reason"] = "fewer than two indicators"
        return None, parts
    return round(sum(parts[k] for k in indicators), 1), parts


def validate_curated(rec: dict[str, Any]) -> list[str]:
    """Problems with the curated (v2) fields of one record."""
    p: list[str] = []
    cat = rec.get("category")
    if cat not in CATEGORIES:
        p.append(f"unknown category {cat!r}")
    if rec.get("tier") not in TIERS:
        p.append(f"tier must be A or B, not {rec.get('tier')!r}")
    if rec.get("region") not in REGIONS:
        p.append(f"unknown region {rec.get('region')!r}")
    if rec.get("platform") and rec["platform"] not in PLATFORMS:
        p.append(f"unknown platform {rec['platform']!r}")
    if rec.get("content_type") and rec["content_type"] not in CONTENT_TYPES:
        p.append(f"unknown content_type {rec['content_type']!r}")

    sel = rec.get("selection") or {}
    if not sel.get("reason"):
        p.append("selection.reason is required")
    for a in sel.get("audience_evidence") or []:
        if a.get("metric") not in AUDIENCE_METRICS:
            p.append(f"unknown audience metric {a.get('metric')!r}")
        if not a.get("source_url"):
            p.append(f"audience figure {a.get('metric')} without source_url")
        if _number(a.get("value")) is None:
            p.append(f"audience figure {a.get('metric')} without a positive value")
    inf = sel.get("influence_evidence") or {}
    for key in ("regional_importance", "cited_by_other_media", "historical_importance"):
        if inf.get(key) and inf[key] not in LEVELS:
            p.append(f"influence_evidence.{key} must be high, medium or low")
    freq = (sel.get("yemen_coverage") or {}).get("frequency")
    if freq and freq not in FREQUENCY_POINTS:
        p.append(f"unknown yemen_coverage.frequency {freq!r}")
    inst = sel.get("institutional_importance") or {}
    if inst.get("level") and inst["level"] not in INSTITUTIONAL_LEVELS:
        p.append(f"unknown institutional_importance {inst['level']!r}")
    if rec.get("tier") == "A" and not (sel.get("audience_evidence") or inf.get("urls")):
        p.append("tier A needs audience_evidence or influence_evidence.urls")
    if rec.get("tier") == "B" and (inst.get("level") not in ("high", "medium") or not inst.get("note")):
        p.append("tier B needs institutional_importance level high/medium with a note")

    al = rec.get("alignment") or {}
    ya = al.get("yemen_political_alignment", "unknown")
    ra = al.get("regional_alignment", "unknown")
    if ya not in YEMEN_ALIGNMENTS:
        p.append(f"unknown yemen_political_alignment {ya!r}")
    if ra not in REGIONAL_ALIGNMENTS:
        p.append(f"unknown regional_alignment {ra!r}")
    if (ya not in NO_CLAIM or ra not in NO_CLAIM) and not al.get("evidence_urls"):
        p.append("alignment without evidence_urls")
    if "none_documented" in (ya, ra) and not al.get("classification_evidence"):
        p.append("none_documented needs classification_evidence saying what was checked")
    conf = al.get("classification_confidence")
    if conf is not None and not (0 <= float(conf) <= 1):
        p.append("classification_confidence must be between 0 and 1")
    if al.get("review_status", "draft") not in REVIEW_STATUSES:
        p.append(f"unknown review_status {al.get('review_status')!r}")

    scores = rec.get("scores") or {}
    if scores.get("reliability_score") is not None and not scores.get("reliability_evidence_urls"):
        p.append("reliability_score without reliability_evidence_urls")
    if scores.get("influence_score") is not None:
        p.append("influence_score is computed by the loader; do not set it by hand")

    if cat == "SOCIAL_ACCOUNT":
        h = rec.get("holder") or {}
        if h.get("public_figure") is not True:
            p.append("SOCIAL_ACCOUNT needs holder.public_figure: true")
        if not h.get("role"):
            p.append("SOCIAL_ACCOUNT needs holder.role")
    for acc in rec.get("accounts") or []:
        if not (acc.get("platform") and acc.get("handle") and acc.get("url")):
            p.append("account without platform, handle or url")
        if not acc.get("handle_evidence"):
            p.append(f"account {acc.get('handle')} without handle_evidence")
        if acc.get("followers") is not None and not acc.get("followers_source"):
            p.append(f"account {acc.get('handle')} has followers without followers_source")
    return p


def content_type_for(rec: dict[str, Any]) -> str:
    return rec.get("content_type") or DEFAULT_CONTENT_TYPE.get(rec.get("category", ""), "journalism")


def default_source_group(rec: dict[str, Any]) -> str:
    """Older views group sources by source_group; derive one for curated records."""
    if rec.get("source_group"):
        return rec["source_group"]
    cat = rec.get("category", "MEDIA")
    region = rec.get("region") or "global"
    if cat == "MEDIA":
        return f"{region}_media"
    return cat.lower()
