"""Regression tests for the Settings page UI wiring (Sprint 8): the served
JS must implement the settings overview render, export/import panel, and
maintenance actions against the new /settings/* endpoints. Same
string-assertion style as test_advisor_search_ui.py (no JS runtime/browser
test harness exists in this repo).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_settings_nav_item_still_present():
    resp = client.get("/")
    assert resp.status_code == 200
    assert 'data-nav="settings"' in resp.text


def test_app_js_implements_settings_page():
    resp = client.get("/static/js/app.js")
    assert resp.status_code == 200
    body = resp.text

    assert "renderSettingsPage" in body
    assert "settings-general" in body
    assert "settings-system" in body
    assert "settings-about" in body
    assert "settings-maintenance" in body


def test_app_js_settings_talks_to_new_endpoints():
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert '"/settings"' in body or "fetchJSON(\"/settings\")" in body
    assert "/settings/export" in body
    assert "/settings/import" in body
    assert "/settings/maintenance/rebuild-graph" in body
    assert "/settings/maintenance/clear-cache" in body


def test_app_js_settings_import_uses_form_data_upload():
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert "settings-import-form" in body
    assert "settings-import-file-input" in body
    assert "wireSettingsActions" in body
