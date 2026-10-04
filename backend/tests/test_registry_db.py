import pytest
import yaml
from sqlalchemy import select

pytestmark = pytest.mark.db

RECORD = {
    "id": "test-embassy",
    "name": "Test Embassy to Yemen",
    "url": "https://embassy.example/",
    "source_type": "diplomatic",
    "category": "DIPLOMATIC_MISSION",
    "tier": "B",
    "region": "gulf",
    "country": "SA",
    "languages": ["ar"],
    "selection": {
        "reason": "Official channel of a state party to the conflict.",
        "institutional_importance": {"level": "high", "note": "Represents an official state position."},
        "audience_evidence": [
            {"metric": "x_followers", "value": 5000, "as_of": "2026-09", "source_url": "https://x.example/e"}
        ],
        "yemen_coverage": {"frequency": "weekly"},
    },
    "alignment": {
        "yemen_political_alignment": "not_applicable",
        "regional_alignment": "saudi",
        "domestic_political_orientation": "state_aligned",
        "classification_confidence": 0.95,
        "classification_evidence": "Embassy of the state.",
        "evidence_urls": ["https://embassy.example/about"],
        "method": "self_description",
        "assessment_date": "2026-10-04",
    },
    "feeds": [{"url": "https://t.me/s/testembassy", "type": "telegram_public", "verified": False}],
}


def test_curated_record_is_stored_with_separate_scores(session, tmp_path):
    from hudhud.db import models as m
    from hudhud.registry.seed import seed_sources

    old = m.Source(slug="test-old", name="Old", url="https://old.example/", source_type="tv", source_group="x")
    session.add(old)
    session.flush()
    (tmp_path / "sources").mkdir()
    (tmp_path / "sources" / "curated.yaml").write_text(yaml.safe_dump([RECORD]))
    stats = seed_sources(session, tmp_path)
    assert stats["sources"] == 1 and stats["invalid"] == 0

    src = session.scalar(select(m.Source).where(m.Source.slug == "test-embassy"))
    assert src.content_type == "official_statement"
    assert src.institutional_importance == "high"
    # 5k followers (7 points) + weekly (15): official status adds nothing.
    assert src.influence_score == 22.0
    assert src.reliability_score is None
    assert src.regional_alignment == "saudi"
    assert src.selection["influence_components"]["rubric"] == "influence-v1"
    cur = next(o for o in src.orientations if o.valid_to is None)
    assert cur.dimensions["regional_alignment"]["value"] == "saudi"

    session.refresh(old)
    assert old.registry_status == "archived" and old.active is False
