"""Regression tests for the ROLE OS First Run Experience: a guided
onboarding wizard that replaces the empty Projects page when zero
projects exist, and a permanent "+ New Project" button once at least one
does. Same string-assertion style as test_cockpit_ui.py / test_launcher_
ui.py (no JS runtime/browser test harness exists in this repo).

Covers, per the five required scenarios: first run, normal mode,
successful creation, API failure, and automatic navigation.
"""

from __future__ import annotations

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


# ---------------------------------------------------------------------------
# First run (zero projects)
# ---------------------------------------------------------------------------


def test_app_js_implements_first_run_onboarding():
    resp = client.get("/static/js/app.js")
    assert resp.status_code == 200
    body = resp.text

    assert "renderFirstRunOnboardingHtml" in body
    assert "first-run-onboarding" in body
    assert "first-run-wizard-form" in body
    assert "Create your first Project" in body


def test_first_run_detection_is_based_on_the_true_unfiltered_total():
    """Zero-projects detection must never be fooled by a workspace
    filter matching nothing -- it has to check the real, unfiltered
    total first."""
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert "allProjectsUnfiltered" in body
    assert "allProjectsUnfiltered.length === 0" in body
    # The detection fetch itself must not carry the workspace filter.
    assert 'fetchJSON("/pi/projects")' in body


# ---------------------------------------------------------------------------
# Normal mode (at least one project exists)
# ---------------------------------------------------------------------------


def test_app_js_implements_permanent_new_project_button_in_normal_mode():
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert "new-project-toggle-btn" in body
    assert "+ New Project" in body
    assert "renderNewProjectFormHtml" in body


def test_normal_mode_reuses_the_same_create_form_fields_as_first_run():
    """Both paths must build their form from the same shared field
    generator -- no duplicated, potentially-diverging form markup."""
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert "renderCreateProjectFieldsHtml" in body
    assert body.count("renderCreateProjectFieldsHtml()") >= 2


# ---------------------------------------------------------------------------
# Successful creation
# ---------------------------------------------------------------------------


def test_creation_posts_to_the_existing_pi_projects_endpoint():
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert 'postJSON("/pi/projects", payload)' in body


def test_successful_creation_shows_success_toast_and_suggests_first_ai_session():
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert 'showToast("Project created. Let\'s start your first AI Session!")' in body


def test_creation_handler_shared_by_both_first_run_and_normal_mode():
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert "handleCreateProjectSubmit" in body
    assert 'handleCreateProjectSubmit(e, "first-run-wizard-status")' in body
    assert 'handleCreateProjectSubmit(e, "new-project-status")' in body


# ---------------------------------------------------------------------------
# API failure
# ---------------------------------------------------------------------------


def test_creation_failure_shows_inline_error_and_does_not_navigate():
    resp = client.get("/static/js/app.js")
    body = resp.text
    # The try/catch around the POST renders an error-box and re-enables
    # the submit button, rather than navigating or toasting success.
    assert "catch (err) {" in body
    assert "submitBtn.disabled = false;" in body
    assert '<p class="error-box">${escapeHtml(err.message)}</p>' in body


def test_empty_project_name_is_rejected_before_any_request():
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert "Project name is required." in body


# ---------------------------------------------------------------------------
# Automatic navigation
# ---------------------------------------------------------------------------


def test_successful_creation_navigates_automatically_to_cockpit():
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert 'navigate("cockpit", project.id)' in body


def test_navigation_to_cockpit_only_happens_after_the_await_resolves():
    """The navigate() call must be positioned after `await postJSON(...)`
    succeeds, and before the surrounding catch block -- not before the
    request, and not inside error handling (see the API-failure tests
    above)."""
    resp = client.get("/static/js/app.js")
    body = resp.text
    await_index = body.index("const project = await postJSON")
    catch_block_index = body.index("} catch (err) {", await_index)
    navigate_call_index = body.index('navigate("cockpit", project.id)')
    assert await_index < navigate_call_index < catch_block_index


# ---------------------------------------------------------------------------
# No browser automation (consistent with every prior AI feature in this app)
# ---------------------------------------------------------------------------


def test_first_run_experience_does_not_automate_browser_or_typing():
    resp = client.get("/static/js/app.js")
    body = resp.text.lower()
    for forbidden in ("playwright", "puppeteer", "selenium", "sendkeys", "keyboard.type"):
        assert forbidden not in body
