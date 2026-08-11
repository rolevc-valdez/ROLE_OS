"""Regression tests for the Workspace Adoption UI (a new SPA page plus an
additive extension to the existing Projects page). Same string-assertion
style as test_first_run_ui.py / test_cockpit_ui.py -- no JS runtime/browser
test harness exists in this repo.
"""

from __future__ import annotations

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_sidebar_has_workspace_nav_item():
    resp = client.get("/")
    assert resp.status_code == 200
    assert 'data-nav="workspace"' in resp.text
    assert "<span>Workspace</span>" in resp.text


def test_app_js_registers_workspace_route():
    resp = client.get("/static/js/app.js")
    assert resp.status_code == 200
    body = resp.text
    assert "workspace: renderWorkspacePage" in body


def test_app_js_implements_workspace_page_requirements():
    body = client.get("/static/js/app.js").text

    # Summary stats (requirement #9)
    assert "Last Scan" in body
    assert "Projects Found" in body
    assert "Projects Adopted" in body
    assert "Ignored Projects" in body

    # Rescan button (requirement #8)
    assert "workspace-rescan-btn" in body
    assert "Rescan Workspace" in body
    assert '"/workspace/rescan"' in body

    # Per-item fields (requirement #3)
    for field in ("item.name", "item.root_path", "item.classification", "workspaceGitLabel", "item.health_score", "item.confidence_score", "item.move_risk"):
        assert field in body

    # Buttons (requirement #4)
    assert "data-workspace-adopt" in body
    assert "data-workspace-ignore" in body
    assert "data-workspace-review" in body
    assert "openWorkspaceReviewDetail" in body


def test_app_js_projects_page_merges_discovered_projects():
    """Requirement #10/#11: Projects page shows discovered/adopted
    top-level projects in addition to (not instead of) manually-created
    ones. Sprint 4 upgraded the data source from `/workspace/adopted`
    (adopted-only, thin shape) to `/workspace/discovered?view=top_level`
    (every top-level project, enriched) -- still fully additive."""
    body = client.get("/static/js/app.js").text
    assert 'fetchJSON("/workspace/discovered?view=top_level")' in body
    assert "discoveredProjects" in body
    assert "workspaceStatusBadge(p)" in body
    # First-run onboarding must require BOTH lists empty, not just the
    # manual one -- otherwise a workspace with only discovered projects
    # would incorrectly show the "create your first project" wizard.
    assert "allProjectsUnfiltered.length === 0 && discoveredProjects.length === 0" in body


def test_view_root_delegation_handles_data_nav_from_rendered_content():
    """Discovered-project cards use data-nav="workspace" inside dynamically
    rendered content, which needs delegation through #view-root (unlike the
    sidebar's [data-nav] items, whose listeners are attached once at boot)."""
    body = client.get("/static/js/app.js").text
    assert 'e.target.closest("[data-nav]")' in body
