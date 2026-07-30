"""Regression tests for the Session page UI wiring (ROLE OS Dashboard MVP):
the served template must have a Session nav item, and the served JS must
implement the Session page's render/wiring functions against the new
/session/* endpoints. Same string-assertion style as test_settings_ui.py
(no JS runtime/browser test harness exists in this repo).
"""

from __future__ import annotations

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_session_nav_item_present():
    resp = client.get("/")
    assert resp.status_code == 200
    assert 'data-nav="session"' in resp.text


def test_app_js_implements_session_page():
    resp = client.get("/static/js/app.js")
    assert resp.status_code == 200
    body = resp.text

    assert "renderSessionPage" in body
    assert "session: renderSessionPage" in body
    assert "renderStartFormHtml" in body
    assert "renderEndFormHtml" in body
    assert "renderPromptCardHtml" in body
    assert "renderCompletedCardHtml" in body
    assert "renderRegistryCardHtml" in body
    assert "renderDecisionsCardHtml" in body


def test_app_js_session_talks_to_new_endpoints():
    resp = client.get("/static/js/app.js")
    body = resp.text
    for endpoint in (
        "/session/modes",
        "/session/registry",
        "/session/current",
        "/session/start",
        "/session/decisions/recent",
    ):
        assert endpoint in body


def test_app_js_session_does_not_hardcode_modes():
    """Requirement: modes are a single reusable source of truth (the
    backend's app/session/modes.py) -- the UI must fetch them, not
    hardcode a second copy of the six mode names/descriptions."""
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert "getModesCached" in body
    assert '"/session/modes"' in body
    # None of the six mode purposes/AI-behavior strings should be
    # duplicated as literal text in the JS -- only their IDs may appear,
    # via the options the fetched data renders.
    assert "Scope a problem, evaluate options" not in body  # PLAN's purpose text, backend-only


def test_app_js_session_wires_copy_and_download():
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert "wireCopyButton" in body
    assert "navigator.clipboard.writeText" in body
    assert "/markdown/download" in body
    assert "save-to-vault" in body
