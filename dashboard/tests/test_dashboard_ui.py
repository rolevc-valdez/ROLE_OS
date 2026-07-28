"""Regression tests for the Dashboard page wiring (Sprint 7): the served
page/JS must include the new nav item, route, metrics mapping, quick
actions, and empty-state handling. Same string-assertion style as
test_conversation_graph_ui.py / test_advisor_search_ui.py (no JS runtime/
browser harness exists in this repo; see dashboard/README.md for the
manual verification performed for actual rendering/interaction behavior).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_sidebar_includes_dashboard_nav_item():
    resp = client.get("/")
    assert resp.status_code == 200
    assert 'data-nav="dashboard"' in resp.text
    # Home is unchanged/untouched as the existing landing page.
    assert 'data-nav="home"' in resp.text


def test_app_js_implements_dashboard_route_and_render_function():
    resp = client.get("/static/js/app.js")
    assert resp.status_code == 200
    body = resp.text
    assert "dashboard: renderDashboardPage" in body
    assert "renderDashboardPage" in body


def test_dashboard_reuses_existing_metrics_endpoint_only():
    """No duplicated calculations: the Dashboard must read the same
    already-computed /import/metrics response the Explorer uses, not
    recompute anything client-side."""
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert '"/import/metrics"' in body
    assert "dashboardMetricsHtml" in body
    for field in (
        "imported_conversations", "metrics.projects", "metrics.people", "metrics.tasks",
        "metrics.decisions", "metrics.ideas", "metrics.documents", "metrics.assets",
        "metrics.graph_nodes", "metrics.graph_edges",
    ):
        assert field in body


def test_dashboard_implements_ten_summary_cards():
    resp = client.get("/static/js/app.js")
    body = resp.text
    start = body.index("function dashboardMetricsHtml")
    end = body.index("function renderDashboardMetrics")
    snippet = body[start:end]
    for label in (
        "Conversations", "Projects", "People", "Tasks", "Decisions",
        "Ideas", "Documents", "Assets", "Graph Nodes", "Graph Edges",
    ):
        assert f'"{label}"' in snippet, label


def test_dashboard_implements_recent_activity_sections():
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert "renderDashboardRecentConversations" in body
    assert "renderDashboardRecentObjects" in body
    assert "/extraction/recent" in body
    assert "/import/conversations" in body


def test_dashboard_implements_system_status():
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert "renderDashboardStatus" in body
    assert "/import/history" in body
    assert "/extraction/runs" in body
    assert "Last import" in body
    assert "Last extraction" in body
    assert "Graph status" in body
    assert "Database status" in body


def test_dashboard_implements_quick_actions():
    resp = client.get("/static/js/app.js")
    body = resp.text
    start = body.index("async function renderDashboardPage")
    end = body.index("routes = {") if "routes = {" in body[start:] else len(body)
    snippet = body[start : start + 3000]
    assert "Import Conversation" in snippet
    assert "Conversation Explorer" in snippet
    assert "Knowledge Graph" in snippet
    assert "Search Knowledge" in snippet
    assert 'data-nav="knowledge"' in snippet
    assert 'data-nav="explorer"' in snippet
    assert 'data-nav="conversation-graph"' in snippet
    assert 'data-nav="advisor"' in snippet


def test_dashboard_handles_empty_state_without_special_backend_call():
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert "No conversations imported yet." in body
    assert "Nothing extracted yet." in body
    assert "No imports yet" in body
    assert "No extraction runs yet" in body
    assert "No graph data yet" in body


def test_dashboard_handles_error_state():
    resp = client.get("/static/js/app.js")
    body = resp.text
    start = body.index("async function renderDashboardPage")
    end = start + 4000
    snippet = body[start:end]
    assert "catch (err)" in snippet
    assert "error-box" in snippet


def test_existing_pages_unaffected_by_dashboard_addition():
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert "renderHome" in body
    assert "renderExplorerPage" in body
    assert "renderConversationGraphPage" in body
    assert "renderAdvisorPage" in body
    assert client.get("/health").status_code == 200
    assert client.get("/import/metrics").status_code == 200
