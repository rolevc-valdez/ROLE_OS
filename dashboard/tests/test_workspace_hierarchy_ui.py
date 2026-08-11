"""Regression tests for the Sprint 3 Workspace page UI additions: filter
tabs, expand/collapse of nested children, and the Review page's override
actions. Same string-assertion style as test_workspace_ui.py -- no JS
runtime/browser test harness exists in this repo (a live browser smoke
test was run manually for this sprint; see the completion report).
"""

from __future__ import annotations

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_filter_tabs_present():
    body = client.get("/static/js/app.js").text
    assert "WORKSPACE_FILTERS" in body
    assert "Top-level projects" in body
    assert "Nested repositories" in body
    assert "Ignored / excluded" in body
    assert "Needs review" in body
    assert "data-workspace-filter" in body


def test_grouped_default_view_requested_from_backend():
    body = client.get("/static/js/app.js").text
    assert "workspaceActiveFilter" in body
    assert '"top_level"' in body
    assert "fetchWorkspaceFilterItems" in body
    assert "view=" in body


def test_expand_collapse_children_present():
    body = client.get("/static/js/app.js").text
    assert "data-workspace-expand" in body
    assert "workspaceExpandedIds" in body
    assert "data-workspace-child-of" in body
    assert "workspace-child-row" in body


def test_status_badge_shows_adopted_discovered_ignored():
    body = client.get("/static/js/app.js").text
    assert "workspaceStatusBadge" in body
    assert "Discovered" in body
    assert "Ignored" in body


def test_top_level_row_shows_child_kind_counts():
    body = client.get("/static/js/app.js").text
    for field in (
        "repository_count",
        "component_count",
        "documentation_count",
        "asset_library_count",
        "internal_folder_count",
    ):
        assert field in body


def test_review_page_shows_boundary_detail_and_override_actions():
    body = client.get("/static/js/app.js").text
    assert "workspaceReviewDetailHtml" in body
    assert "Detected-boundary evidence" in body
    assert "data-workspace-override-top" in body
    assert "data-workspace-override-ignore" in body
    assert "data-workspace-clear-override" in body
    assert "/override" in body
