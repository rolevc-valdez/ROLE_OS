"""Tests for the server-rendered UI shell and its additive `/ui/*` JSON
endpoints.

Epic 4 replaced the Milestone 2/3 tab-based page with a Command Center
shell (persistent sidebar + header, client-side hash routing rendered by
app.js) — the old `data-tab="..."` panels and their fixed-content ids
(`#project-list`, `#card-list`, `#pi-project-list`, `#graph-tab`, ...) no
longer exist server-side because that content is now rendered dynamically
by JavaScript after the page loads. What this file still verifies, and
must keep verifying regardless of UI redesigns: the page renders, the
static assets are served, the `/ui/*` endpoints work, and every existing
API route is unaffected.
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
    assert 'id="app-shell"' in body
    assert 'id="view-root"' in body
    assert 'id="detail-overlay"' in body


def test_dashboard_page_links_static_assets():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "/static/css/style.css" in resp.text
    assert "/static/js/app.js" in resp.text


def test_static_css_served():
    resp = client.get("/static/css/style.css")
    assert resp.status_code == 200
    assert "text/css" in resp.headers["content-type"]


def test_static_js_served():
    resp = client.get("/static/js/app.js")
    assert resp.status_code == 200
    assert "javascript" in resp.headers["content-type"]


def test_design_system_css_files_served():
    """Epic 4: the reusable design system is split into colors/layout/
    components/animations, each independently servable, and pulled in by
    style.css via @import."""
    for name in ("colors.css", "layout.css", "components.css", "animations.css"):
        resp = client.get(f"/static/css/{name}")
        assert resp.status_code == 200, name
        assert "text/css" in resp.headers["content-type"]

    style_resp = client.get("/static/css/style.css")
    body = style_resp.text
    for name in ("colors.css", "layout.css", "components.css", "animations.css"):
        assert name in body


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


def test_dashboard_page_includes_command_center_sidebar():
    """Epic 4: a persistent sidebar with an icon per section replaces the
    old tab bar."""
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.text

    assert 'id="sidebar"' in body
    for nav in ("home", "projects", "knowledge", "advisor", "graph", "assets", "settings"):
        assert f'data-nav="{nav}"' in body, nav


def test_dashboard_page_includes_command_center_header():
    """Epic 4: header has global search, workspace selector, a live
    date/time element, and quick actions."""
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.text

    assert 'id="global-search-input"' in body
    assert 'id="header-workspace-select"' in body
    assert 'id="header-datetime"' in body
    assert 'class="quick-actions"' in body


def test_static_js_implements_command_center_router_and_views():
    """Epic 4: app.js now drives a hash-based router with dedicated view
    renderers for every page in the spec, and still talks to the same
    Graph API introduced in Epic 3 (no backend change)."""
    resp = client.get("/static/js/app.js")
    assert resp.status_code == 200
    body = resp.text

    assert "hashchange" in body
    assert "renderHome" in body
    assert "renderProjectsList" in body
    assert "renderProjectDetail" in body
    assert "renderAdvisorPage" in body
    assert "renderGraphPage" in body
    assert "renderAssetsPage" in body
    assert "renderSettingsPage" in body

    # Still built entirely on the existing, unmodified APIs.
    assert "/graph/neighbors/" in body
    assert "/graph/path" in body
    assert "/graph/impact/" in body
    assert "/advisor/recommendations" in body
    assert "/pi/projects" in body
