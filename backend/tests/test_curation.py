from hudhud.registry import curation
from hudhud.registry.seed import _orientation_block, validate_source


def _rec(**over):
    rec = {
        "id": "example-mofa",
        "name": "Example Ministry of Foreign Affairs",
        "url": "https://mofa.example/",
        "source_type": "government",
        "category": "OFFICIAL_GOVERNMENT",
        "tier": "B",
        "region": "gulf",
        "selection": {
            "reason": "Official foreign-policy voice of a state involved in Yemen.",
            "institutional_importance": {"level": "high", "note": "Party to the conflict."},
            "audience_evidence": [
                {
                    "metric": "x_followers",
                    "value": 2000,
                    "as_of": "2026-09",
                    "source_url": "https://x.example",
                }
            ],
            "yemen_coverage": {"frequency": "monthly"},
        },
        "alignment": {
            "yemen_political_alignment": "not_applicable",
            "regional_alignment": "saudi",
            "domestic_political_orientation": "state_aligned",
            "classification_confidence": 0.95,
            "classification_evidence": "It is the government's own ministry.",
            "evidence_urls": ["https://mofa.example/"],
            "method": "self_description",
        },
    }
    rec.update(over)
    return rec


def test_valid_official_record():
    assert validate_source(_rec()) == []


def test_official_status_does_not_raise_influence():
    # 2k followers + monthly Yemen statements: low influence, high institutional importance.
    sel = {**_rec()["selection"], "influence_evidence": {"regional_importance": "high", "historical_importance": "high"}}
    score, parts = curation.influence(sel, "B")
    assert score == 11.0  # reach 3 + monthly 8; institutional ratings are not scored for tier B
    assert parts["reach"] == 3.0
    assert parts["not_scored"] == ["regional_importance", "historical_importance"]
    assert "institutional_importance" not in parts


def test_no_influence_score_without_audience_figure():
    score, parts = curation.influence(
        {"yemen_coverage": {"frequency": "daily"}, "influence_evidence": {"cited_by_other_media": "high"}}
    )
    assert score is None and parts["reason"] == "no citable audience figure"


def test_influence_needs_two_indicators():
    score, parts = curation.influence(
        {"audience_evidence": [{"metric": "x_followers", "value": 10**7, "source_url": "https://x"}]}
    )
    assert score is None and parts["reach"] == 40


def test_influence_full_marks():
    score, _ = curation.influence(
        {
            "audience_evidence": [
                {"metric": "monthly_visits", "value": 5 * 10**7, "source_url": "https://s"}
            ],
            "yemen_coverage": {"frequency": "daily"},
            "influence_evidence": {
                "regional_importance": "high",
                "cited_by_other_media": "high",
                "historical_importance": "high",
            },
        }
    )
    assert score == 100.0


def test_alignment_requires_evidence():
    rec = _rec()
    rec["alignment"] = {**rec["alignment"], "evidence_urls": []}
    assert "alignment without evidence_urls" in validate_source(rec)


def test_none_documented_needs_what_was_checked():
    rec = _rec()
    rec["alignment"] = {
        "yemen_political_alignment": "none_documented",
        "regional_alignment": "not_applicable",
    }
    assert any("none_documented" in p for p in validate_source(rec))


def test_reliability_cannot_be_set_without_evidence():
    assert "reliability_score without reliability_evidence_urls" in validate_source(
        _rec(scores={"reliability_score": 0.9})
    )


def test_tier_rules():
    no_inst = _rec()
    no_inst["selection"] = {**no_inst["selection"], "institutional_importance": {"level": "low"}}
    assert any("tier B" in p for p in validate_source(no_inst))
    media = _rec(category="MEDIA", tier="A")
    media["selection"] = {"reason": "Large audience."}
    assert any("tier A" in p for p in validate_source(media))


def test_social_account_must_be_public_figure():
    rec = _rec(category="SOCIAL_ACCOUNT", tier="B", holder={"kind": "person", "role": "Minister"})
    assert any("public_figure" in p for p in validate_source(rec))


def test_account_handles_need_evidence():
    rec = _rec(accounts=[{"platform": "x", "handle": "mofa", "url": "https://x.com/mofa"}])
    assert any("handle_evidence" in p for p in validate_source(rec))


def test_content_type_defaults():
    assert curation.content_type_for(_rec()) == "official_statement"
    assert curation.content_type_for(_rec(category="DIPLOMATIC_MISSION")) == "official_statement"
    assert (
        curation.content_type_for(_rec(category="INTERNATIONAL_INSTITUTION")) == "institutional_publication"
    )
    assert curation.content_type_for(_rec(category="MEDIA")) == "journalism"


def test_alignment_goes_to_orientation_history():
    o = _orientation_block(_rec())
    assert o["simplified"] == "state_aligned"
    assert o["dimensions"]["regional_alignment"]["value"] == "saudi"
    assert "yemen_political_alignment" in o["dimensions"]
    assert o["evidence_urls"] == ["https://mofa.example/"]
