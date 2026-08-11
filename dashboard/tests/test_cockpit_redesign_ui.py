"""Regression tests for UX Sprint UX-001 "Cockpit Redesign": turns the
Cockpit from an administration form into a daily work dashboard --
project header, a prominent Resume Work button, a collapsed-by-default
New AI Session form, promoted current sessions, an iconified timeline,
and secondary actions tucked behind overflow menus. The original Today's
Objective / Next Action / Last Snapshot insight cards were themselves
replaced by the Project Memory card in Sprint C7.1 (Resume Work Refactor)
-- see that section below.

Same string-assertion style as test_cockpit_ui.py (no JS runtime/browser
test harness exists in this repo) -- this file covers the redesign on
top of, not instead of, test_cockpit_ui.py, which is left untouched and
must keep passing unmodified.
"""

from __future__ import annotations

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


# ---------------------------------------------------------------------------
# Project header
# ---------------------------------------------------------------------------


def test_cockpit_header_shows_project_name_workspace_status_and_last_activity():
    resp = client.get("/static/js/app.js")
    assert resp.status_code == 200
    body = resp.text
    assert "cockpit-header" in body
    assert "cockpit-header-main" in body
    assert "cockpit-header-meta" in body
    assert "cockpit-header-actions" in body
    assert "Last activity:" in body


# ---------------------------------------------------------------------------
# Resume Work prominence
# ---------------------------------------------------------------------------


def test_resume_work_button_is_prominent_and_primary():
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert 'id="cockpit-resume-work-btn"' in body
    assert "btn-resume-work" in body
    # It must be styled as a primary action, not a secondary/overflow one.
    assert 'class="btn btn-primary btn-resume-work"' in body
    assert "Resume Work" in body


def test_resume_work_button_reuses_the_existing_resume_wiring():
    """It should drive the same generic [data-resume] handler as the
    per-session Resume buttons -- no separate/duplicated resume logic."""
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert 'data-resume="${escapeHtml(currentSession.id)}"' in body
    assert 'querySelectorAll("[data-resume]")' in body


# ---------------------------------------------------------------------------
# Collapsed state (default)
# ---------------------------------------------------------------------------


def test_new_ai_session_form_is_collapsed_by_default():
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert '<form id="cockpit-new-session-form" hidden>' in body
    assert 'id="cockpit-new-session-toggle-btn"' in body
    assert "+ New AI Session" in body


# ---------------------------------------------------------------------------
# Expanded state (on click)
# ---------------------------------------------------------------------------


def test_new_ai_session_form_expands_only_via_its_toggle_button():
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert 'getElementById("cockpit-new-session-toggle-btn").addEventListener("click"' in body
    assert "newSessionForm.hidden = !newSessionForm.hidden;" in body


# ---------------------------------------------------------------------------
# Auto-collapse after successful creation
# ---------------------------------------------------------------------------


def test_new_ai_session_form_auto_collapses_after_successful_creation():
    resp = client.get("/static/js/app.js")
    body = resp.text
    submit_idx = body.index('newSessionForm.addEventListener("submit"')
    post_idx = body.index(
        "await postJSON(`/pi/projects/${encodeURIComponent(projectId)}/ai-sessions`, payload);",
        submit_idx,
    )
    collapse_idx = body.index(
        'document.getElementById("cockpit-new-session-form").hidden = true;', post_idx
    )
    rerender_idx = body.index("await renderCockpitPage(projectId);", collapse_idx)
    # Order matters: create -> collapse -> re-render, all inside the try block.
    assert submit_idx < post_idx < collapse_idx < rerender_idx


def test_new_ai_session_creation_failure_does_not_auto_collapse():
    resp = client.get("/static/js/app.js")
    body = resp.text
    submit_idx = body.index('newSessionForm.addEventListener("submit"')
    catch_idx = body.index("} catch (err) {", submit_idx)
    collapse_idx = body.index(
        'document.getElementById("cockpit-new-session-form").hidden = true;', submit_idx
    )
    # The collapse call must be inside the try block, before the catch.
    assert submit_idx < collapse_idx < catch_idx


# ---------------------------------------------------------------------------
# Promote current AI sessions
# ---------------------------------------------------------------------------


def test_current_sessions_are_sorted_to_the_top():
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert "sessionsRaw].sort((a, b) => (b.current ? 1 : 0) - (a.current ? 1 : 0))" in body


def test_current_session_card_gets_a_distinct_style_and_badge():
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert "cockpit-session-current" in body
    assert 'badge badge-info">&#9679; Current</span>' in body


# ---------------------------------------------------------------------------
# Timeline with icons
# ---------------------------------------------------------------------------


def test_timeline_entries_render_an_icon():
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert "function timelineIcon(entryType)" in body
    assert '<span class="timeline-icon" aria-hidden="true">${timelineIcon(e.type)}</span>' in body


# ---------------------------------------------------------------------------
# Project Memory (Sprint C7.1): replaces the old Today's Objective / Next
# Action / Last Snapshot insight cards as Cockpit's primary card. The AI
# Session is a transport, never the source of truth -- see
# `docs/product/DECISIONS.md`.
# ---------------------------------------------------------------------------


def test_project_memory_card_is_cockpits_primary_card():
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert "function renderProjectMemoryCardHtml(memory)" in body
    assert 'id="cockpit-project-memory-card"' in body
    assert "Where We Left Off" in body
    assert "Pending Work" in body
    assert "Next Action" in body
    assert "/memory`)" in body  # fetches GET /pi/projects/{id}/memory


def test_project_memory_card_renders_before_ai_sessions_becomes_secondary():
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert body.index("renderProjectMemoryCardHtml(projectMemory)") < body.index(
        "<h2>AI Sessions</h2>"
    )


# ---------------------------------------------------------------------------
# Overflow menu for secondary actions
# ---------------------------------------------------------------------------


def test_session_secondary_actions_are_hidden_behind_an_overflow_menu():
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert 'data-overflow-menu="${escapeHtml(s.id)}" hidden>' in body
    assert "data-overflow-toggle" in body
    # All the pre-existing secondary actions must still exist, just moved
    # inside the collapsible overflow menu.
    menu_start = body.index('data-overflow-menu="${escapeHtml(s.id)}" hidden>')
    menu_end = body.index("</div>", menu_start)
    menu_html = body[menu_start:menu_end]
    for action in (
        "data-open-session",
        "data-favorite",
        "data-snapshot-toggle",
        "data-delete-session",
    ):
        assert action in menu_html


def test_page_level_overflow_menu_holds_the_project_switcher():
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert 'id="cockpit-overflow-menu" hidden>' in body
    assert 'id="cockpit-overflow-toggle-btn"' in body
    assert "cockpit-project-select" in body


# ---------------------------------------------------------------------------
# Responsive layout
# ---------------------------------------------------------------------------


def test_cockpit_uses_the_responsive_home_grid():
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert '<div class="home-grid u-mt-4">' in body


def test_css_defines_responsive_rules_for_the_cockpit_header():
    resp = client.get("/static/css/layout.css")
    assert resp.status_code == 200
    css = resp.text
    assert "@media (max-width: 1100px)" in css
    media_block = css[css.index("@media (max-width: 1100px)") :]
    assert ".cockpit-header" in media_block
    assert ".home-grid" in media_block


def test_css_defines_the_cockpit_header_and_overflow_menu_classes():
    resp = client.get("/static/css/components.css")
    assert resp.status_code == 200
    css = resp.text
    for selector in (
        ".cockpit-header",
        ".cockpit-header-actions",
        ".btn-resume-work",
        ".overflow-menu",
        ".timeline-icon",
    ):
        assert selector in css


# ---------------------------------------------------------------------------
# Preserve existing functionality: no backend/API/DB surface changed
# ---------------------------------------------------------------------------


def test_redesign_still_talks_only_to_existing_ai_sessions_and_timeline_endpoints():
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert "/ai-sessions`" in body
    assert "/timeline`" in body
    assert "/resume`" in body
    assert "/set-current`" in body
    assert "/snapshots`" in body


def test_no_browser_automation_introduced():
    resp = client.get("/static/js/app.js")
    body = resp.text.lower()
    for forbidden in ("playwright", "puppeteer", "selenium", "sendkeys", "keyboard.type"):
        assert forbidden not in body
