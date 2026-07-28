"""Regression tests for the Advisor Search UI wiring (Sprint 6): the
served JS must include the search section's markup hooks and cross-links
to the Conversation Explorer and Knowledge Graph pages. Same
string-assertion style as test_conversation_graph_ui.py (no JS runtime/
browser test harness exists in this repo; see dashboard/README.md for the
manual verification performed for actual rendering/interaction behavior).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_advisor_page_still_served_and_unredesigned():
    """The sidebar nav item and page route are unchanged -- Sprint 6 adds
    a section to the existing Advisor page, it doesn't introduce a new
    nav item or route."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert 'data-nav="advisor"' in resp.text


def test_app_js_implements_advisor_search_section():
    resp = client.get("/static/js/app.js")
    assert resp.status_code == 200
    body = resp.text

    assert "advisor-search-input" in body
    assert "advisor-search-type-select" in body
    assert "advisor-search-clear-btn" in body
    assert "advisor-search-results" in body
    assert "wireAdvisorSearch" in body


def test_app_js_advisor_search_talks_to_new_endpoint_only():
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert "/advisor/search" in body
    # Existing Epic 2 endpoints must still be present and untouched.
    assert "/advisor/recommendations" in body
    assert "/advisor/daily-brief" in body


def test_app_js_advisor_search_cross_links_explorer_and_graph():
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert "data-advisor-open-conversation" in body
    assert "data-advisor-open-graph" in body
    assert "pendingExplorerConversationFocus" in body
    assert 'navigate("conversation-graph"' in body


def test_components_css_defines_advisor_search_results_scroll():
    resp = client.get("/static/css/components.css")
    assert resp.status_code == 200
    assert ".advisor-search-results" in resp.text
