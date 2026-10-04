"""Load the YAML seed registry into the database (idempotent upserts).

Run: ``hudhud seed``. Editing the YAML and re-running updates rows in place;
orientation changes close the previous orientation row (valid_to) and open a new one,
so the orientation history is preserved.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import structlog
import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from hudhud.config import get_settings
from hudhud.db import models as m
from hudhud.nlp.text import normalize_for_matching
from hudhud.registry import curation

log = structlog.get_logger()

SIMPLIFIED_LABELS = {
    "far_left",
    "left",
    "center_left",
    "center",
    "center_right",
    "right",
    "far_right",
    "progressive",
    "conservative",
    "religious_conservative",
    "religious_progressive",
    "nationalist",
    "liberal",
    "socialist",
    "islamist",
    "secular",
    "monarchist",
    "revolutionary",
    "state_aligned",
    "movement_aligned",
    "independent",
    "mixed",
    "unknown",
    # institutional categories that fit international media better than ideology labels
    "state_funded",
    "public_service",
    "intergovernmental",
    "opposition_aligned",
}
LABEL_ALIASES = {
    "state_media": "state_aligned",
    "state_owned": "state_aligned",
    "party_aligned": "movement_aligned",
}
METHODS = {
    "manual_research",
    "academic_source",
    "media_watchdog",
    "ownership_analysis",
    "editorial_analysis",
    "hyperlink_network",
    "LLM_assisted",
    "community_annotation",
    "self_description",
    "unknown",
}
OPERATING_BASES = {"sanaa_controlled", "government_controlled", "stc_controlled", "outside_yemen", "unknown"}


def _load(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _as_date(value: Any) -> dt.date | None:
    if value in (None, ""):
        return None
    if isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(str(value))


# ---------------------------------------------------------------- languages


def seed_languages(session: Session, seeds: Path) -> int:
    rows = _load(seeds / "languages.yaml")
    for r in rows:
        lang = session.get(m.Language, r["code"]) or m.Language(code=r["code"])
        lang.name_en, lang.name_native, lang.script = r["en"], r.get("native"), r["script"]
        lang.rtl, lang.supported = bool(r.get("rtl")), r.get("supported", True)
        session.add(lang)
    session.flush()
    return len(rows)


# ---------------------------------------------------------------- sources


def validate_source(rec: dict[str, Any]) -> list[str]:
    """Return a list of problems with one source record (empty when valid)."""
    problems = []
    for key in ("id", "name", "url", "source_type"):
        if not rec.get(key):
            problems.append(f"missing {key}")
    o = _orientation_block(rec)
    label = LABEL_ALIASES.get(o.get("simplified", "unknown"), o.get("simplified", "unknown"))
    if label not in SIMPLIFIED_LABELS:
        problems.append(f"unknown orientation label {label!r}")
    if label != "unknown" and not o.get("evidence_urls"):
        problems.append("orientation label without evidence_urls")
    if o.get("method", "unknown") not in METHODS:
        problems.append(f"unknown orientation method {o.get('method')!r}")
    if rec.get("operating_base", "unknown") not in OPERATING_BASES:
        problems.append(f"unknown operating_base {rec.get('operating_base')!r}")
    problems += curation.validate_curated(rec)
    return problems


def _orientation_block(rec: dict[str, Any]) -> dict[str, Any]:
    """The orientation row for a record.

    Curated records describe classification in ``alignment``; it is stored in the
    orientation history table so changes over time stay visible. ``simplified`` is the
    domestic political orientation label (measure A shorthand).
    """
    al = rec.get("alignment")
    if not al:
        return rec.get("orientation") or {}
    dims: dict[str, Any] = {}
    conf = float(al.get("classification_confidence") or 0.0)
    for key in ("yemen_political_alignment", "regional_alignment", "domestic_political_orientation"):
        if al.get(key) and al[key] != "unknown":
            dims[key] = {"value": al[key], "confidence": conf}
    if al.get("sub_alignment"):
        dims["sub_alignment"] = {"value": al["sub_alignment"], "confidence": conf}
    simplified = al.get("domestic_political_orientation") or "unknown"
    simplified = LABEL_ALIASES.get(simplified, simplified)
    return {
        "simplified": simplified if simplified in SIMPLIFIED_LABELS else "unknown",
        "dimensions": dims,
        "confidence": conf,
        "evidence": al.get("classification_evidence") or "",
        "evidence_urls": list(al.get("evidence_urls") or []),
        "method": al.get("method", "unknown"),
        "last_reviewed": al.get("assessment_date"),
        "review_status": al.get("review_status", "draft"),
    }


def _default_operating_base(rec: dict[str, Any]) -> str:
    if rec.get("operating_base"):
        return rec["operating_base"]
    if rec.get("country") and rec["country"] != "YE":
        return "outside_yemen"
    return {"yemen_state_sanaa": "sanaa_controlled", "yemen_state_irg": "government_controlled"}.get(
        rec.get("source_group", ""), "unknown"
    )


def upsert_source(session: Session, rec: dict[str, Any], today: dt.date | None = None) -> m.Source:
    today = today or dt.date.today()
    src = session.scalar(select(m.Source).where(m.Source.slug == rec["id"]))
    if src is None:
        src = m.Source(slug=rec["id"])
        session.add(src)
    src.name = rec["name"]
    src.name_native = rec.get("name_native")
    src.url = rec["url"]
    src.domain = (urlparse(rec["url"]).hostname or "").removeprefix("www.") or None
    src.country = (rec.get("country") or None) if rec.get("country") != "XX" else None
    src.source_type = rec["source_type"]
    src.source_group = curation.default_source_group(rec)
    src.geographic_focus = list(rec.get("geographic_focus") or [])
    src.operating_base = _default_operating_base(rec)
    src.yemen_coverage = rec.get("yemen_coverage")
    own = rec.get("ownership") or {}
    src.ownership_description = own.get("description") or None
    src.ownership_evidence_urls = list(own.get("evidence_urls") or [])
    src.access_policy = rec.get("access_policy", "metadata_only")
    src.active = bool(rec.get("active", True))
    src.notes = rec.get("notes") or None
    _apply_curation(src, rec)
    if not src.active:
        src.health_status = "inactive"
    session.flush()

    # languages
    wanted = set(rec.get("languages") or [])
    known = {code for (code,) in session.execute(select(m.Language.code))}
    src.languages = [m.SourceLanguage(source_id=src.id, language_code=c) for c in sorted(wanted & known)]

    # feeds (unique by URL across the registry)
    for f in rec.get("feeds") or []:
        feed = session.scalar(select(m.SourceFeed).where(m.SourceFeed.url == f["url"]))
        if feed is None:
            feed = m.SourceFeed(url=f["url"], source_id=src.id)
            session.add(feed)
        feed.source_id = src.id
        feed.feed_type = f.get("type", "rss")
        feed.verified = bool(f.get("verified"))
        feed.verified_at = _as_date(f.get("verified_at"))
        feed.yemen_filter = bool(f.get("yemen_filter"))
        feed.active = bool(f.get("active", True)) and src.active
        feed.notes = f.get("notes") or None

    _upsert_orientation(session, src, _orientation_block(rec), today)
    return src


def _apply_curation(src: m.Source, rec: dict[str, Any]) -> None:
    sel = dict(rec.get("selection") or {})
    al = rec.get("alignment") or {}
    score, components = curation.influence(sel, rec.get("tier"))
    sel["influence_components"] = components
    src.category = rec.get("category", "MEDIA")
    src.tier = rec.get("tier")
    src.region = rec.get("region")
    src.platform = rec.get("platform")
    src.content_type = curation.content_type_for(rec)
    src.wikidata = rec.get("wikidata")
    src.yemen_political_alignment = al.get("yemen_political_alignment", "unknown")
    src.regional_alignment = al.get("regional_alignment", "unknown")
    src.sub_alignment = al.get("sub_alignment") or None
    src.domestic_political_orientation = al.get("domestic_political_orientation")
    src.classification_confidence = (
        float(al["classification_confidence"]) if al.get("classification_confidence") is not None else None
    )
    src.assessment_date = _as_date(al.get("assessment_date"))
    src.institutional_importance = (sel.get("institutional_importance") or {}).get("level")
    src.influence_score = score
    scores = rec.get("scores") or {}
    # Reliability is NOT ASSESSED unless evidence is cited; never inferred from category.
    src.reliability_score = (
        float(scores["reliability_score"])
        if scores.get("reliability_score") is not None and scores.get("reliability_evidence_urls")
        else None
    )
    src.selection = _jsonable(sel)
    src.accounts = _jsonable(list(rec.get("accounts") or []))
    src.holder = _jsonable(rec.get("holder")) if rec.get("holder") else None
    src.registry_status = "curated"


def _jsonable(value: Any) -> Any:
    """YAML gives dates as date objects; JSONB columns need strings."""
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, dt.date):
        return value.isoformat()
    return value


def _upsert_orientation(session: Session, src: m.Source, o: dict[str, Any], today: dt.date) -> None:
    label = LABEL_ALIASES.get(o.get("simplified", "unknown"), o.get("simplified", "unknown"))
    if label not in SIMPLIFIED_LABELS:
        label = "unknown"
    urls = list(o.get("evidence_urls") or [])
    if label != "unknown" and not urls:
        # Never store an unevidenced label.
        log.warning("orientation_without_evidence", source=src.slug, label=label)
        label = "unknown"
    payload = {
        "simplified": label,
        "dimensions": o.get("dimensions") or {},
        "confidence": float(o.get("confidence") or 0.0),
        "evidence": o.get("evidence") or None,
        "method": o.get("method", "unknown") if o.get("method", "unknown") in METHODS else "unknown",
        "review_status": o.get("review_status", "draft"),
        "last_reviewed": _as_date(o.get("last_reviewed")),
    }
    current = session.scalar(
        select(m.SourceOrientation).where(
            m.SourceOrientation.source_id == src.id, m.SourceOrientation.valid_to.is_(None)
        )
    )
    signature = (payload["simplified"], payload["dimensions"], round(payload["confidence"], 3), sorted(urls))
    if current is not None:
        current_sig = (
            current.simplified,
            current.dimensions,
            round(current.confidence, 3),
            sorted(e.url for e in current.evidence_items),
        )
        if current_sig == signature:
            current.evidence, current.method = payload["evidence"], payload["method"]
            current.review_status, current.last_reviewed = payload["review_status"], payload["last_reviewed"]
            return
        current.valid_to = today
    row = m.SourceOrientation(source_id=src.id, valid_from=today, **payload)
    row.evidence_items = [
        m.SourceOrientationEvidence(url=u, accessed_at=payload["last_reviewed"]) for u in urls
    ]
    session.add(row)


def seed_sources(session: Session, seeds: Path) -> dict[str, int]:
    """Load ``sources/*.yaml`` (not ``sources/archive/``) and archive everything else.

    A non-demo source that is no longer in the curated registry is marked archived and
    inactive, so it stops being collected; its articles and history are kept.
    """
    stats = {"sources": 0, "invalid": 0, "archived": 0}
    seen: set[str] = set()
    for path in sorted((seeds / "sources").glob("*.yaml")):
        for rec in _load(path) or []:
            problems = validate_source(rec)
            if problems or rec.get("id") in seen:
                stats["invalid"] += 1
                log.warning(
                    "invalid_source_record",
                    file=path.name,
                    id=rec.get("id"),
                    problems=problems or ["duplicate id"],
                )
                continue
            seen.add(rec["id"])
            upsert_source(session, rec)
            stats["sources"] += 1
    session.flush()
    if seen:
        stale = session.scalars(
            select(m.Source).where(
                m.Source.slug.not_in(seen),
                m.Source.is_demo.is_(False),
                m.Source.registry_status != "archived",
            )
        )
        for src in stale:
            src.registry_status, src.active, src.health_status = "archived", False, "inactive"
            for feed in src.feeds:
                feed.active = False
            stats["archived"] += 1
    session.flush()
    return stats


# ---------------------------------------------------------------- taxonomy & frames


def seed_taxonomy(session: Session, seeds: Path) -> int:
    count = 0

    def upsert(node: dict[str, Any], parent: m.Category | None, level: int) -> None:
        nonlocal count
        cat = session.scalar(select(m.Category).where(m.Category.slug == node["slug"]))
        if cat is None:
            cat = m.Category(slug=node["slug"])
            session.add(cat)
        cat.name_en, cat.name_ar = node["en"], node.get("ar")
        cat.parent_id, cat.level = (parent.id if parent else None), level
        cat.keywords = node.get("kw") or {}
        cat.description = node.get("description")
        session.flush()
        count += 1
        for child in node.get("children") or []:
            upsert(child, cat, level + 1)

    for node in _load(seeds / "taxonomy.yaml"):
        upsert(node, None, 0)
    return count


def seed_frames(session: Session, seeds: Path) -> int:
    rows = _load(seeds / "frames.yaml")
    for r in rows:
        fr = session.scalar(select(m.Frame).where(m.Frame.slug == r["slug"])) or m.Frame(slug=r["slug"])
        fr.name_en, fr.name_ar, fr.description = r["en"], r.get("ar"), r.get("description")
        fr.cues = {"hypothesis": r.get("hypothesis"), **(r.get("cues") or {})}
        session.add(fr)
    session.flush()
    return len(rows)


# ---------------------------------------------------------------- entities & locations


def _upsert_entity(session: Session, slug: str, **fields: Any) -> m.Entity:
    ent = session.scalar(select(m.Entity).where(m.Entity.slug == slug))
    if ent is None:
        ent = m.Entity(slug=slug)
        session.add(ent)
    for k, v in fields.items():
        setattr(ent, k, v)
    session.flush()
    return ent


def _set_aliases(
    session: Session, ent: m.Entity, aliases: list[list[str]], extra: list[tuple[str, str]]
) -> None:
    existing = {(a.normalized_form, a.language): a for a in ent.aliases}
    wanted: dict[tuple[str, str], m.EntityAlias] = {}
    entries = [(a[0], a[1], a[2] if len(a) > 2 else "common", a[3] if len(a) > 3 else None) for a in aliases]
    entries += [(form, lang, "official", None) for form, lang in extra]
    for form, lang, atype, note in entries:
        key = (normalize_for_matching(form), lang)
        if key in wanted:
            continue
        alias = existing.get(key) or m.EntityAlias(entity_id=ent.id)
        alias.surface_form, alias.normalized_form, alias.language = form, key[0], lang
        alias.alias_type, alias.framing_note = atype, note
        alias.match = len(key[0]) >= 3
        wanted[key] = alias
    ent.aliases = list(wanted.values())


def seed_entities(session: Session, seeds: Path) -> int:
    rows = _load(seeds / "entities.yaml")
    by_slug: dict[str, m.Entity] = {}
    for r in rows:
        ent = _upsert_entity(
            session,
            r["slug"],
            entity_type=r["type"],
            subtype=r.get("subtype"),
            name_en=r["en"],
            name_ar=r.get("ar"),
            description=r.get("description"),
            is_public_figure=True,
        )
        _set_aliases(session, ent, r.get("aliases") or [], [])
        by_slug[r["slug"]] = ent
    for r in rows:
        if r.get("parent") and r["parent"] in by_slug:
            by_slug[r["slug"]].parent_id = by_slug[r["parent"]].id
    session.flush()
    return len(rows)


def seed_locations(session: Session, seeds: Path) -> int:
    data = _load(seeds / "locations.yaml")
    govs: dict[str, m.Entity] = {}
    n = 0
    for g in data["governorates"]:
        ent = _upsert_entity(
            session,
            f"gov-{g['slug']}",
            entity_type="location",
            subtype="governorate",
            name_en=g["en"],
            name_ar=g.get("ar"),
            description=f"Capital: {g.get('capital')}",
        )
        _set_aliases(session, ent, g.get("aliases") or [], [(g["en"], "en"), (g["ar"], "ar")])
        loc = session.get(m.Location, ent.id) or m.Location(entity_id=ent.id)
        loc.location_type, loc.admin_code, loc.lat, loc.lon = "governorate", g["code"], g["lat"], g["lon"]
        loc.governorate_entity_id = ent.id
        session.add(loc)
        govs[g["slug"]] = ent
        n += 1
    session.flush()
    for p in data["places"]:
        ent = _upsert_entity(
            session,
            f"place-{p['slug']}",
            entity_type="location",
            subtype=p["type"],
            name_en=p["en"],
            name_ar=p.get("ar"),
        )
        _set_aliases(session, ent, p.get("aliases") or [], [(p["en"], "en"), (p["ar"], "ar")])
        loc = session.get(m.Location, ent.id) or m.Location(entity_id=ent.id)
        loc.location_type, loc.lat, loc.lon = p["type"], p.get("lat"), p.get("lon")
        gov = govs.get(p.get("governorate", ""))
        loc.governorate_entity_id = gov.id if gov else None
        session.add(loc)
        n += 1
    session.flush()
    return n


def seed_models(session: Session, seeds: Path) -> int:
    rows = _load(seeds / "models.yaml")
    for r in rows:
        mod = session.scalar(select(m.Model).where(m.Model.name == r["name"])) or m.Model(name=r["name"])
        mod.provider, mod.license, mod.url, mod.description = (
            r["provider"],
            r.get("license"),
            r.get("url"),
            r.get("description"),
        )
        session.add(mod)
        session.flush()
        for t in r.get("tasks") or []:
            session.merge(m.ModelTask(model_id=mod.id, task=t))
        for lang in r.get("languages") or []:
            session.merge(m.ModelLanguage(model_id=mod.id, language_code=lang))
    session.flush()
    return len(rows)


def seed_all(session: Session, seeds: Path | None = None) -> dict[str, Any]:
    seeds = seeds or get_settings().seeds_dir
    stats: dict[str, Any] = {"languages": seed_languages(session, seeds)}
    stats.update(seed_sources(session, seeds))
    stats["categories"] = seed_taxonomy(session, seeds)
    stats["frames"] = seed_frames(session, seeds)
    stats["entities"] = seed_entities(session, seeds)
    stats["locations"] = seed_locations(session, seeds)
    stats["models"] = seed_models(session, seeds)
    return stats
