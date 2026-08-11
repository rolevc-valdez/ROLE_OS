"""Regression tests for the Dashboard page wiring.

Sprint 7 built the legacy, zero-centric Dashboard (Explorer's own
`/import/metrics` counts of extracted knowledge objects, honestly zero
until ChatGPT conversations are imported). Sprint C2 (Dashboard 2.0)
replaced it with an executive dashboard powered by `GET /dashboard/summary`
(ProjectContext + Home/Advisor/Activity/Assets/Knowledge). These tests
were rewritten for C2 -- see `test_dashboard_v2.py` for the substantive
data-correctness tests; this file covers page wiring/structure. Same
string-assertion style as the other *_ui.py files (no JS runtime/browser
harness exists in this repo; see dashboard/README.md for the manual
verification performed for actual rendering/interaction behavior).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_sidebar_includes_dashboard_nav_item():
    resp = client.get("/")
    assert resp.status_code == 200
    assert 'data-nav="dashboard"' in resp.text
    # Home is unchanged/untouched as the existing landing page.
    assert 'data-nav="home"' in resp.text


def test_app_js_implements_dashboard_route_and_render_function():
    resp = client.get("/static/js/app.js")
    assert resp.status_code == 200
    body = resp.text
    assert "dashboard: renderDashboardPage" in body
    assert "renderDashboardPage" in body


def test_dashboard_uses_dashboard_summary_endpoint_only():
    """Sprint C2: the Dashboard now reads the one already-shaped
    `/dashboard/summary` endpoint, not Explorer's `/import/metrics`, and
    performs no client-side recalculation of health/next-action/
    recommendation-priority/resume-availability (all embedded, canonical,
    per project)."""
    resp = client.get("/static/js/app.js")
    body = resp.text
    dashboard_fn = body.split("async function renderDashboardPage")[1].split(
        "PROJECTS LIST + FIRST RUN EXPERIENCE"
    )[0]
    assert '"/dashboard/summary"' in dashboard_fn
    assert '"/import/metrics"' not in dashboard_fn


def test_dashboard_implements_executive_summary_cards():
    resp = client.get("/static/js/app.js")
    body = resp.text
    start = body.index("function dashCardsHtml")
    end = body.index("function renderDashCards")
    snippet = body[start:end]
    for label in (
        "Adopted Projects",
        "Healthy",
        "Needs Attention",
        "Dirty Repositories",
        "With Next Action",
        "Active AI Sessions",
        "Recent Snapshots",
        "Reusable Assets",
        "Knowledge Cards",
        "Recent Commits",
    ):
        assert f'"{label}"' in snippet, label


def test_dashboard_implements_portfolio_status_groups():
    resp = client.get("/static/js/app.js")
    body = resp.text
    start = body.index("function renderDashPortfolioStatus")
    end = start + 2000
    snippet = body[start:end]
    for key in ("healthy", "critical", "warning", "active", "inactive", "launch_ready"):
        assert f'"{key}"' in snippet, key


def test_dashboard_implements_continue_work_and_needs_attention_and_activity():
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert "renderDashContinueWork" in body
    assert "renderDashNeedsAttention" in body
    assert "renderDashRecentActivity" in body
    assert "renderDashRecentAssets" in body
    assert "renderDashRecentKnowledge" in body
    assert "Resume Work" in body
    assert "data-resume-work-item" in body


def test_dashboard_frontend_does_not_recompute_canonical_fields():
    """§10: the frontend must be presentation-only -- it reads `ctx.health`/
    `ctx.next_action`/`ctx.resume_state` directly rather than recomputing a
    tier from a raw score or re-deriving a next-action string."""
    resp = client.get("/static/js/app.js")
    body = resp.text
    dashboard_section = body[
        body.index("DASHBOARD 2.0 (Sprint C2)") : body.index("PROJECTS LIST + FIRST RUN EXPERIENCE")
    ]
    assert "ctx.health" in dashboard_section
    assert "ctx.next_action" in dashboard_section
    assert "ctx.resume_state" in dashboard_section
    # No score-based tier recomputation anywhere in this section.
    assert "healthTier(" not in dashboard_section


def test_dashboard_handles_empty_states_honestly():
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert "No reusable assets detected." in body
    assert "Knowledge has not been imported yet." in body
    assert "No recent activity yet." in body
    assert "Nothing needs attention right now." in body


def test_dashboard_handles_error_state():
    resp = client.get("/static/js/app.js")
    body = resp.text
    start = body.index("async function renderDashboardPage")
    end = start + 4000
    snippet = body[start:end]
    assert "catch (err)" in snippet
    assert "error-box" in snippet


def test_existing_pages_unaffected_by_dashboard_rewrite():
    resp = client.get("/static/js/app.js")
    body = resp.text
    assert "renderHome" in body
    assert "renderExplorerPage" in body
    assert "renderConversationGraphPage" in body
    assert "renderAdvisorPage" in body
    assert client.get("/health").status_code == 200
    # Explorer's own metrics endpoint is untouched -- only the Dashboard
    # page stopped using it as its data source.
    assert client.get("/import/metrics").status_code == 200
