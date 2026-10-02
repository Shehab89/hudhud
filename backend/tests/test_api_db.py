import csv
import io

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.db
ADMIN = {"X-Admin-Token": "test-admin-token"}


@pytest.fixture(scope="module")
def client(demo_db):
    from observatory.api.main import create_app

    with TestClient(create_app()) as c:
        yield c


@pytest.mark.parametrize(
    "path",
    [
        "/health",
        "/openapi.json",
        "/api/v1/overview",
        "/api/v1/timeline?split=operating_base",
        "/api/v1/timeline?split=sentiment",
        "/api/v1/articles?limit=5",
        "/api/v1/articles?q=cholera",
        "/api/v1/search?q=Red%20Sea%20shipping",
        "/api/v1/search?q=الكوليرا&mode=keyword",
        "/api/v1/categories",
        "/api/v1/trends",
        "/api/v1/topic-models",
        "/api/v1/topics",
        "/api/v1/sources?limit=5",
        "/api/v1/actors",
        "/api/v1/actors/ansar-allah",
        "/api/v1/terminology?entity=ansar-allah",
        "/api/v1/events",
        "/api/v1/geography",
        "/api/v1/media-landscape",
        "/api/v1/compare/narratives",
        "/api/v1/meta",
        "/api/v1/models",
        "/api/v1/quality",
    ],
)
def test_public_endpoints_respond(client, path):
    r = client.get(path)
    assert r.status_code == 200, r.text[:300]
    assert r.headers["X-Content-Type-Options"] == "nosniff"


def test_article_detail_keeps_the_five_concepts_apart(client):
    aid = client.get("/api/v1/articles?limit=1").json()["items"][0]["id"]
    body = client.get(f"/api/v1/articles/{aid}").json()
    for key in ("source", "sentiment", "frames", "topics", "categories", "targeted_sentiment"):
        assert key in body, key
    assert "bias_score" not in str(body)
    assert body["is_demo"] is True


def test_demo_filter(client):
    assert client.get("/api/v1/articles?demo=exclude").json()["total"] == 0
    assert client.get("/api/v1/articles?demo=only").json()["total"] > 0


def test_invalid_filters_are_rejected(client):
    assert client.get("/api/v1/articles?date_from=2026-01-01&date_to=2025-01-01").status_code == 422
    assert client.get("/api/v1/timeline?split=nonsense").status_code == 422
    assert client.get("/api/v1/articles/999999999").status_code == 404


def test_csv_export_guards_against_formula_injection(client):
    r = client.get("/api/v1/export/articles?format=csv&limit=20")
    assert r.status_code == 200
    rows = list(csv.reader(io.StringIO(r.text.lstrip("﻿"))))
    assert len(rows) > 1
    for row in rows[1:]:
        for cell in row:
            assert not cell.startswith(("=", "+", "@")) or cell[:1] == "'"


@pytest.mark.parametrize(("fmt", "marker"), [("bibtex", "@misc{"), ("ris", "TY  - "), ("json", "[")])
def test_citation_exports(client, fmt, marker):
    r = client.get(f"/api/v1/export/articles?format={fmt}&limit=3")
    assert r.status_code == 200
    assert marker in r.text


def test_admin_requires_token(client):
    assert client.get("/api/v1/admin/runs").status_code == 401
    assert client.get("/api/v1/admin/runs", headers={"X-Admin-Token": "wrong"}).status_code == 401
    runs = client.get("/api/v1/admin/runs", headers=ADMIN)
    assert runs.status_code == 200


def test_saved_queries_need_an_api_key(client, demo_db):
    from observatory.api.deps import hash_api_key
    from observatory.db import models as m

    assert client.get("/api/v1/saved-queries").status_code == 401
    demo_db.add(
        m.User(email="researcher@example.org", api_key_hash=hash_api_key("obs_test"), role="researcher")
    )
    demo_db.commit()
    h = {"X-API-Key": "obs_test"}
    created = client.post(
        "/api/v1/saved-queries", headers=h, json={"name": "Red Sea", "query": {"q": "Red Sea"}}
    )
    assert created.status_code == 201, created.text
    assert [q["name"] for q in client.get("/api/v1/saved-queries", headers=h).json()] == ["Red Sea"]
    assert client.delete(f"/api/v1/saved-queries/{created.json()['id']}", headers=h).status_code == 204


def test_accepted_correction_becomes_the_current_result(client, demo_db):
    from observatory.api.deps import hash_api_key
    from observatory.db import models as m

    demo_db.add(m.User(email="annotator@example.org", api_key_hash=hash_api_key("obs_ann"), role="annotator"))
    demo_db.commit()
    aid = client.get("/api/v1/articles?limit=1").json()["items"][0]["id"]
    before = client.get(f"/api/v1/articles/{aid}").json()["sentiment"]
    new = "positive" if [x["polarity"] for x in before] != ["positive"] else "negative"
    r = client.post(
        "/api/v1/annotations",
        headers={"X-API-Key": "obs_ann"},
        json={"article_id": aid, "target_type": "sentiment", "corrected_value": {"polarity": new}},
    )
    assert r.status_code == 201, r.text
    ann = r.json()["id"]
    r = client.patch(f"/api/v1/admin/annotations/{ann}", headers=ADMIN, json={"status": "accepted"})
    assert r.json() == {"id": ann, "status": "accepted", "applied": True}
    after = client.get(f"/api/v1/articles/{aid}").json()["sentiment"]
    assert [(x["polarity"], x["method"]) for x in after] == [(new, "human")]
    assert (
        client.patch(
            f"/api/v1/admin/annotations/{ann}", headers=ADMIN, json={"status": "rejected"}
        ).status_code
        == 409
    )
