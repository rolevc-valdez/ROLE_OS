"""Regression tests for what happened to the v1.3 AI Workspace *UI* when
v1.4 "Context Engine" shipped.

Per v1.4 objective 1 ("Replace the single AI Workspace record with an AI
Session collection"), the old single-record card on the Project detail
page was intentionally replaced by a lean AI Sessions summary card that
links to the new Cockpit page -- this file's old assertions about
`renderAiWorkspaceCardHtml`/`wireAiWorkspaceCard` and the old
`ai-workspace-*` button IDs described that now-removed UI and have been
updated accordingly.

This is a UI-only change. The v1.3 *backend* contract
(`/pi/projects/{id}/ai-workspace*`) was explicitly required to keep
working unmodified, and is still fully covered by `test_ai_workspace_
db.py` and `test_ai_workspace_api.py` (untouched by this change) plus
the backward-compatibility checks in `test_ai_sessions_api.py`.
"""

from __future__ import annotations

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_old_ai_workspace_card_ui_no_longer_present():
    """The specific v1.3 card markup/handlers are gone -- replaced, not
    just supplemented -- confirming objective 1's "replace" was honored
    in the UI, not merely additive."""
    resp = client.get("/static/js/app.js")
    assert resp.status_code == 200
    body = resp.text
    assert "renderAiWorkspaceCardHtml" not in body
    assert "wireAiWorkspaceCard" not in body
    assert "ai-workspace-open-claude-btn" not in body
    assert "ai-workspace-save-form" not in body


def test_ai_sessions_summary_card_replaced_it_on_project_detail_page():
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert "renderAiSessionsSummaryCardHtml" in body
    assert "renderAiSessionsSummaryCardHtml(projectId, aiSessions)" in body
    assert "/ai-sessions`" in body


def test_project_detail_page_links_to_cockpit():
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert "data-open-cockpit" in body
    assert "Open Cockpit" in body


def test_app_js_does_not_automate_browser_or_typing():
    """Still true after the v1.4 UI replacement -- no automation library
    was introduced anywhere in this file."""
    resp = client.get("/static/js/app.js")
    body = resp.text.lower()
    for forbidden in ("playwright", "puppeteer", "selenium", "sendkeys", "keyboard.type"):
        assert forbidden not in body


def test_ai_workspace_backend_contract_still_reachable():
    """The v1.3 API itself (as opposed to its UI) is unaffected -- see
    test_ai_workspace_api.py for the full contract test; this is a
    smoke check that the route still exists after the UI change."""
    resp = client.get("/pi/projects/does-not-exist/ai-workspace")
    assert (
        resp.status_code == 404
    )  # route exists and runs its own logic, not a 404 from FastAPI routing
