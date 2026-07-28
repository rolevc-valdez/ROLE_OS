"""Regression tests for the Knowledge Graph UI wiring (Sprint 5): the
served page/JS must include the new nav item, route, and cross-links to
the Conversation Explorer. Same string-assertion style as test_ui.py
(the current test architecture has no JS runtime/browser test harness, so
this is the deepest automated coverage available for client-side wiring;
see dashboard/README.md for the manual verification performed for the
actual rendering/interaction behavior).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_sidebar_includes_knowledge_graph_nav_item():
    resp = client.get("/")
    assert resp.status_code == 200
    assert 'data-nav="conversation-graph"' in resp.text
    assert "Knowledge Graph" in resp.text


def test_app_js_implements_conversation_graph_route_and_view():
    resp = client.get("/static/js/app.js")
    assert resp.status_code == 200
    body = resp.text

    assert '"conversation-graph": renderConversationGraphPage' in body
    assert "renderConversationGraphPage" in body
    assert "createGraphView" in body  # reuses the existing rendering engine

    # Talks to the new API, not the Epic 3 /graph API.
    assert "/conversation-graph" in body
    assert "/conversation-graph/nodes/" in body


def test_app_js_implements_explorer_graph_cross_links():
    resp = client.get("/static/js/app.js")
    body = resp.text

    # Explorer -> Knowledge Graph
    assert "explorer-detail-view-graph-btn" in body
    assert 'navigate("conversation-graph"' in body

    # Knowledge Graph -> Explorer
    assert "kg-open-conversation-btn" in body
    assert "pendingExplorerConversationFocus" in body


def test_colors_css_defines_new_node_type_colors():
    resp = client.get("/static/css/colors.css")
    assert resp.status_code == 200
    body = resp.text
    assert "--node-task" in body
    assert "--node-idea" in body
    assert "--node-document" in body
