"""Regression tests for the AI Launcher UI wiring (ROLE OS v1.2): the
served JS must implement the three launcher buttons and the toast, and
talk only to /launcher/start. Same string-assertion style as
test_session_ui.py (no JS runtime/browser test harness exists here).
"""

from __future__ import annotations

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_app_js_implements_ai_launcher_card():
    resp = client.get("/static/js/app.js")
    assert resp.status_code == 200
    body = resp.text

    assert "renderAiLauncherCardHtml" in body
    assert "ai-launch-claude-btn" in body
    assert "ai-launch-chatgpt-btn" in body
    assert "ai-launch-both-btn" in body
    assert "Start Claude" in body
    assert "Start ChatGPT" in body
    assert "Start Both" in body


def test_app_js_ai_launcher_talks_to_launcher_endpoint():
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert '"/launcher/start"' in body


def test_app_js_ai_launcher_copies_clipboard_and_opens_urls():
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert "navigator.clipboard.writeText(result.prompt)" in body
    assert 'window.open(url, "_blank")' in body


def test_app_js_ai_launcher_shows_the_required_toast_message():
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert "Prompt copied. Press Ctrl+V and Enter." in body
    assert "showToast" in body


def test_app_js_ai_launcher_does_not_automate_typing_or_browser_interaction():
    """v1.2 explicitly does not automate typing or drive the browser --
    confirms no automation library or keystroke-simulation call was
    introduced alongside the launcher."""
    resp = client.get("/static/js/app.js")
    body = resp.text.lower()
    for forbidden in ("playwright", "puppeteer", "selenium", "sendkeys", "keyboard.type"):
        assert forbidden not in body


def test_ai_launcher_card_wired_into_active_session_branch():
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert "wireAiLauncher" in body
    assert "renderAiLauncherCardHtml()" in body
