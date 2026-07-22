"""Tests for the server-rendered UI routes added in Milestone 2.

Verifies the dashboard page renders, static assets are served, and the
small additive `/ui/*` JSON endpoints work — without touching the existing
`/health`, `/projects`, `/search`, and `/knowledge/{id}` API tests in
test_api.py.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_dashboard_page_renders():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    body = resp.text
    assert "ROLE OS" in body
    assert 'id="search-input"' in body
    assert 'id="project-list"' in body
    assert 'id="card-list"' in body
    assert 'id="timeline-list"' in body
    assert 'id="detail-overlay"' in body


def test_dashboard_page_links_static_assets():
    resp = client.get("/")
    assert resp.status_code == 200
    assert '/static/css/style.css' in resp.text
    assert '/static/js/app.js' in resp.text


def test_static_css_served():
    resp = client.get("/static/css/style.css")
    assert resp.status_code == 200
    assert "text/css" in resp.headers["content-type"]


def test_static_js_served():
    resp = client.get("/static/js/app.js")
    assert resp.status_code == 200
    assert "javascript" in resp.headers["content-type"]


def test_ui_recent_returns_cards():
    resp = client.get("/ui/recent")
    assert resp.status_code == 200
    cards = resp.json()
    assert isinstance(cards, list)
    assert len(cards) >= 1
    assert cards[0]["conversation_id"] == "conv-1"


def test_ui_recent_respects_limit():
    resp = client.get("/ui/recent", params={"limit": 1})
    assert resp.status_code == 200
    assert len(resp.json()) <= 1


def test_ui_timeline_returns_entries():
    resp = client.get("/ui/timeline")
    assert resp.status_code == 200
    entries = resp.json()
    assert isinstance(entries, list)
    assert len(entries) >= 1
    entry = entries[0]
    assert set(entry.keys()) == {"conversation_id", "title", "project", "date", "updated"}


def test_existing_api_routes_unchanged():
    # Milestone 1 endpoints must keep working exactly as before.
    assert client.get("/health").status_code == 200
    assert client.get("/projects").status_code == 200
    assert client.get("/search", params={"q": "Master"}).status_code == 200
    assert client.get("/knowledge/conv-1").status_code == 200
    assert client.get("/knowledge/does-not-exist").status_code == 404
