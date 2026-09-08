"""Regression tests for Sprint 5's frontend additions: the shared
`triggerResumeWork` helper, the Resume Work button on Discovered Project
Detail, Timeline section, Quick Resume/Advisor wiring to Resume Work, and
the Projects page's dedup of canonical-linked manual rows. Same string-
assertion style as the other *_ui.py files -- no JS runtime/browser test
harness exists in this repo (a live browser smoke test was run manually
for this sprint; see the completion report).
"""

from __future__ import annotations

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_shared_trigger_resume_work_helper_present():
    body = client.get("/static/js/app.js").text
    # Hotfix (Session Intent no-action guard): gained an optional second
    # parameter (`userObjective`) for re-calling itself once the Cockpit
    # guard prompt is answered -- the original single-argument call sites
    # (below) still work unchanged, since the new parameter is optional.
    assert "async function triggerResumeWork(itemId, userObjective)" in body
    assert "/resume-work" in body
    assert "navigator.clipboard.writeText" in body
    assert 'navigate("cockpit", result.project_id)' in body


def test_discovered_project_detail_has_resume_work_button():
    body = client.get("/static/js/app.js").text
    assert "dproject-resume-work-btn" in body
    assert "Resume Work" in body
    assert "triggerResumeWork(item.id)" in body


def test_discovered_project_detail_has_timeline_section():
    body = client.get("/static/js/app.js").text
    assert "dprojectTimelineHtml" in body
    assert '"Timeline"' in body


def test_home_quick_resume_triggers_resume_work_not_just_navigation():
    body = client.get("/static/js/app.js").text
    assert "data-resume-work-item" in body
    # Sprint 6 null-safety hardening reads `home.quick_resume` through the
    # centralized `safeObj()` helper (`qr.item_id`) rather than the raw
    # nested path -- see test_home_portfolio_null_safety.py.
    assert "qr.item_id" in body


def test_advisor_recommendations_link_to_resume_work():
    body = client.get("/static/js/app.js").text
    assert "rec.item_id" in body
    assert "Resume Work" in body


def test_session_intent_modal_close_button_only_hides_the_overlay():
    """Session Intent Routing trace (2026-08-11): the modal's close ("x")
    button must never call `triggerResumeWork`, `launchClaudeCode`, or
    `openWebAssistant` -- canceling must not launch anything. Static-source
    assertion (no JS runtime harness in this repo, same convention as the
    rest of this file) that the close handler's body is exactly the hide,
    nothing else, before the next real statement begins."""
    body = client.get("/static/js/app.js").text
    marker = 'document.getElementById("objective-close").addEventListener("click", () => {'
    start = body.index(marker) + len(marker)
    end = body.index("});", start)
    handler_body = body[start:end]
    assert handler_body.strip() == "objectiveOverlay.hidden = true;"


def test_start_session_button_resumes_the_same_resume_work_call():
    """The Session Intent modal must be a clarification step, not a dead
    end: "Start Session" re-invokes the shared `triggerResumeWork` helper
    with the supplied objective, so the response can carry
    `execution_target`/`working_directory`/a real prompt straight through
    to the Resume With chooser or Claude Code launch -- no separate
    workflow, no second Resume Work click."""
    body = client.get("/static/js/app.js").text
    assert 'id="objective-submit-btn">Start Session</button>' in body
    marker = 'document.getElementById("objective-submit-btn").addEventListener("click", async () => {'
    start = body.index(marker)
    end = body.index("});", start)
    handler_body = body[start:end]
    assert "await triggerResumeWork(itemId, userObjective);" in handler_body


def test_projects_page_dedupes_canonical_linked_manual_projects():
    body = client.get("/static/js/app.js").text
    assert "isManualOnly" in body
    assert "discovery_item_id" in body
