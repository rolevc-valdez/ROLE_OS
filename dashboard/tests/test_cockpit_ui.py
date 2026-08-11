"""Regression tests for the Cockpit page UI wiring (ROLE OS v1.4 "Context
Engine"): the served template must have a Cockpit nav item, and the
served JS must implement the unified Cockpit page (sessions, snapshots,
resume, timeline) against the new /pi/projects/{id}/ai-sessions* and
/pi/projects/{id}/timeline endpoints, without introducing any browser
automation. Same string-assertion style as test_session_ui.py /
test_launcher_ui.py (no JS runtime/browser test harness exists here).
"""

from __future__ import annotations

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_cockpit_nav_item_present():
    resp = client.get("/")
    assert resp.status_code == 200
    assert 'data-nav="cockpit"' in resp.text


def test_app_js_implements_cockpit_page():
    resp = client.get("/static/js/app.js")
    assert resp.status_code == 200
    body = resp.text

    assert "renderCockpitPage" in body
    assert "cockpit: renderCockpitPage" in body
    assert "wireCockpitPage" in body


def test_app_js_cockpit_implements_new_session_form():
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert "cockpit-new-session-form" in body
    assert 'name="assistant"' in body
    assert 'name="title"' in body
    assert 'name="conversation_url"' in body
    assert 'name="role"' in body
    assert 'name="preferred_model"' in body
    assert 'name="notes"' in body


def test_app_js_cockpit_implements_session_actions():
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert "data-resume" in body
    assert "data-open-session" in body
    assert "data-favorite" in body
    assert "data-set-current" in body
    assert "data-snapshot-toggle" in body
    assert "data-delete-session" in body


def test_app_js_cockpit_implements_snapshot_fields():
    resp = client.get("/static/js/app.js")
    body = resp.text
    for field in (
        "accomplishments",
        "blockers",
        "pending_work",
        "next_prompt",
        "decisions",
        "summary",
    ):
        assert f'name="{field}"' in body


def test_app_js_cockpit_implements_project_timeline():
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert "renderProjectTimelineHtml" in body
    assert "/timeline`" in body
    assert "Project Timeline" in body


def test_app_js_cockpit_resume_copies_clipboard_and_opens_url():
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert "navigator.clipboard.writeText(result.prompt)" in body
    assert "Prompt copied. Press Ctrl+V and Enter." in body


def test_app_js_cockpit_talks_to_ai_sessions_endpoints_only():
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert "/ai-sessions`" in body
    assert "/resume`" in body
    assert "/set-current`" in body
    assert "/snapshots`" in body


def test_app_js_cockpit_does_not_automate_browser_or_typing():
    resp = client.get("/static/js/app.js")
    body = resp.text.lower()
    for forbidden in ("playwright", "puppeteer", "selenium", "sendkeys", "keyboard.type"):
        assert forbidden not in body
