from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["database_connected"] is True


def test_projects():
    resp = client.get("/projects")
    assert resp.status_code == 200
    projects = resp.json()
    assert isinstance(projects, list)
    assert any(p["project"] == "ROLE_MASTER_FACTORY" for p in projects)


def test_search():
    resp = client.get("/search", params={"q": "ROLE Master"})
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) >= 1
    assert results[0]["project"] == "ROLE_MASTER_FACTORY"


def test_search_requires_query():
    resp = client.get("/search")
    assert resp.status_code == 422


def test_knowledge_card_found():
    resp = client.get("/knowledge/conv-1")
    assert resp.status_code == 200
    card = resp.json()
    assert card["conversation_id"] == "conv-1"
    assert card["title"] == "ROLE Master Factory planning"


def test_knowledge_card_not_found():
    resp = client.get("/knowledge/does-not-exist")
    assert resp.status_code == 404
