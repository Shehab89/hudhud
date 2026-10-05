"""Write the public source-selection table from the curated registry.

    python scripts/registry_table.py

Reads database/seeds/sources/*.yaml (the curated registry; archive/ is not read) and
writes two files:

* docs/source-selection.md: one table per category, for reading;
* docs/source-selection.csv: one row per source with the selection-record fields.

Influence is computed with the same rubric the loader uses (hudhud.registry.curation),
so the table always matches what the platform shows. Nothing here is typed in by hand.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from hudhud.registry import curation  # noqa: E402

CATEGORY_TITLE = {
    "MEDIA": "Media",
    "SOCIAL_ACCOUNT": "Social accounts (public figures)",
    "POLITICAL_ORGANIZATION": "Political organisations",
    "OFFICIAL_GOVERNMENT": "Official government sources",
    "DIPLOMATIC_MISSION": "Diplomatic missions",
    "INTERNATIONAL_INSTITUTION": "International institutions",
    "THINK_TANK": "Think tanks",
    "RESEARCH_ORGANIZATION": "Research organisations",
}
CSV_FIELDS = [
    "source_id",
    "source_name",
    "source_category",
    "tier",
    "country",
    "region",
    "language",
    "platform",
    "selection_reason",
    "audience_evidence",
    "influence_evidence",
    "yemen_coverage",
    "institutional_importance",
    "yemen_political_alignment",
    "sub_alignment",
    "regional_alignment",
    "domestic_political_orientation",
    "influence_score",
    "influence_components",
    "reliability_score",
    "classification_confidence",
    "classification_evidence",
    "evidence_urls",
    "assessment_date",
    "collected_feeds",
    "accounts",
    "active",
]


def load() -> list[dict]:
    recs = []
    for path in sorted((ROOT / "database/seeds/sources").glob("*.yaml")):
        recs += [r for r in yaml.safe_load(path.read_text()) or [] if isinstance(r, dict)]
    return recs


def _audience(sel: dict) -> str:
    return "; ".join(
        f"{a.get('metric')}={a.get('value')} ({a.get('as_of', '')}) {a.get('source_url', '')}".strip()
        for a in sel.get("audience_evidence") or []
    )


def _influence_evidence(sel: dict) -> str:
    inf = sel.get("influence_evidence") or {}
    parts = [
        f"{k}={inf[k]}"
        for k in ("regional_importance", "cited_by_other_media", "historical_importance")
        if inf.get(k)
    ]
    if inf.get("note"):
        parts.append(inf["note"])
    parts += inf.get("urls") or []
    return "; ".join(str(p) for p in parts)


def _feeds(rec: dict) -> list[str]:
    if rec.get("active") is False:
        return []
    return sorted({f.get("type", "rss") for f in rec.get("feeds") or [] if f.get("active", True)})


def row(rec: dict) -> dict:
    sel = rec.get("selection") or {}
    al = rec.get("alignment") or {}
    score, parts = curation.influence(sel, rec.get("tier"))
    inst = sel.get("institutional_importance") or {}
    cov = sel.get("yemen_coverage") or {}
    rel = (rec.get("scores") or {}).get("reliability_score")
    return {
        "source_id": rec["id"],
        "source_name": rec.get("name", ""),
        "source_category": rec.get("category", ""),
        "tier": rec.get("tier", ""),
        "country": rec.get("country", ""),
        "region": rec.get("region", ""),
        "language": ",".join(rec.get("languages") or []),
        "platform": rec.get("platform", ""),
        "selection_reason": sel.get("reason", ""),
        "audience_evidence": _audience(sel),
        "influence_evidence": _influence_evidence(sel),
        "yemen_coverage": " ".join(x for x in (cov.get("frequency"), cov.get("evidence")) if x),
        "institutional_importance": " ".join(x for x in (inst.get("level"), inst.get("note")) if x),
        "yemen_political_alignment": al.get("yemen_political_alignment", "unknown"),
        "sub_alignment": al.get("sub_alignment", ""),
        "regional_alignment": al.get("regional_alignment", "unknown"),
        "domestic_political_orientation": al.get("domestic_political_orientation", ""),
        "influence_score": "" if score is None else score,
        "influence_components": "; ".join(
            f"{k}={v}" for k, v in parts.items() if k not in ("rubric", "reach_basis")
        ),
        "reliability_score": "not assessed" if rel is None else rel,
        "classification_confidence": al.get("classification_confidence", ""),
        "classification_evidence": al.get("classification_evidence", ""),
        "evidence_urls": " ".join(al.get("evidence_urls") or []),
        "assessment_date": str(al.get("assessment_date", "")),
        "collected_feeds": ",".join(_feeds(rec)),
        "accounts": " ".join(f"{a.get('platform')}:{a.get('handle')}" for a in rec.get("accounts") or []),
        "active": rec.get("active", True),
    }


def _cell(text: object, limit: int = 0) -> str:
    s = str(text if text is not None else "").replace("|", "/").replace("\n", " ").strip()
    return s if not limit or len(s) <= limit else s[: limit - 1].rstrip() + "…"


def markdown(rows: list[dict]) -> str:
    by_cat: dict[str, list[dict]] = {}
    for r in rows:
        by_cat.setdefault(r["source_category"], []).append(r)
    scored = sum(1 for r in rows if r["influence_score"] != "")
    collected = sum(1 for r in rows if r["collected_feeds"])
    out = [
        "# Source selection",
        "",
        "Generated by `scripts/registry_table.py` from `database/seeds/sources/*.yaml`. Do not edit by hand.",
        "The same data, with every selection-record field, is in [source-selection.csv](source-selection.csv).",
        "",
        "Hudhud monitors a curated set of high-impact and institutionally important sources, not every",
        "outlet that mentions Yemen. **Tier A** sources were selected for audience and influence, **tier B**",
        "for institutional importance. Influence is computed from cited audience figures and Yemen-coverage",
        "evidence (rubric `influence-v1`, see `database/seeds/sources/SCHEMA.md`); a blank score means the",
        "evidence is too thin to score, not that the source has no influence. Being official raises neither",
        "influence nor reliability, and reliability is not assessed for any source unless evidence is cited.",
        "Alignment records documented affiliation or editorial position; it says nothing about accuracy.",
        "",
        f"Sources: **{len(rows)}**. Influence scored: {scored}. Collected by the pipeline now: {collected}.",
        "",
        "| Category | Tier A | Tier B | Collected |",
        "|---|---:|---:|---:|",
    ]
    order = [c for c in CATEGORY_TITLE if c in by_cat] + sorted(set(by_cat) - set(CATEGORY_TITLE))
    for cat in order:
        rs = by_cat[cat]
        out.append(
            f"| {CATEGORY_TITLE.get(cat, cat)} | {sum(r['tier'] == 'A' for r in rs)} | "
            f"{sum(r['tier'] == 'B' for r in rs)} | {sum(bool(r['collected_feeds']) for r in rs)} |"
        )
    for cat in order:
        rs = sorted(
            by_cat[cat],
            key=lambda r: (r["tier"], -(r["influence_score"] or -1), r["source_name"].lower()),
        )
        out += [
            "",
            f"## {CATEGORY_TITLE.get(cat, cat)}",
            "",
            "| Source | Country | Tier | Influence | Institutional | Yemeni camp | Regional | Collected | Why selected |",
            "|---|---|---|---:|---|---|---|---|---|",
        ]
        for r in rs:
            inst = r["institutional_importance"].split(" ", 1)[0] if r["institutional_importance"] else ""
            out.append(
                f"| {_cell(r['source_name'])} | {r['country']} | {r['tier']} | {r['influence_score']} | "
                f"{inst} | {r['yemen_political_alignment']} | {r['regional_alignment']} | "
                f"{r['collected_feeds'] or 'no'} | {_cell(r['selection_reason'], 160)} |"
            )
    return "\n".join(out) + "\n"


def main() -> None:
    rows = [row(r) for r in load()]
    docs = ROOT / "docs"
    with (docs / "source-selection.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        w.writeheader()
        w.writerows(rows)
    (docs / "source-selection.md").write_text(markdown(rows), encoding="utf-8")
    print(f"{len(rows)} sources written to docs/source-selection.md and docs/source-selection.csv")


if __name__ == "__main__":
    main()
