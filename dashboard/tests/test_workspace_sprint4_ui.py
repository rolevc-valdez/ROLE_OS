"""Regression tests for Sprint 4's frontend additions: Home portfolio,
Discovered Project Detail, Advisor's Workspace section, and the rebuilt
Assets page. Same string-assertion style as the other *_ui.py files -- no
JS runtime/browser test harness exists in this repo (a live browser smoke
test was run manually for this sprint; see the completion report).
"""

from __future__ import annotations

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_home_page_has_portfolio_section():
    body = client.get("/static/js/app.js").text
    assert "renderHomePortfolio" in body
    assert '"/workspace/home"' in body
    assert "Your Projects" in body
    assert "Quick Resume" in body


def test_recent_assets_renderer_uses_real_asset_field_not_summary():
    """Regression: `home.recent_assets` items are raw
    `assets_index.AssetRecord` dicts (filename/project/...), never an
    activity-feed-shaped `summary` field. The renderer must read
    `.filename`, not call `.replace()` on a `summary` field that doesn't
    exist on this object (see test_home_portfolio_null_safety.py and
    test_workspace_portfolio.py's
    `test_recent_assets_preserves_real_asset_record_shape` for the
    backend-side contract)."""
    body = client.get("/static/js/app.js").text
    portfolio_fn = body.split("async function renderHomePortfolio")[1].split(
        "function renderTodaysFocus"
    )[0]
    assert "asset.filename" in portfolio_fn
    assert "asset.summary" not in portfolio_fn


def test_home_portfolio_uses_centralized_null_safe_formatters():
    """Regression: the Home portfolio renderer (and its
    `homeProjectMiniCardHtml` helper) must route every field it displays
    through the centralized `fmtText`/`fmtDate`/`safeArr`/`safeObj`
    helpers rather than scattered ad hoc `?? ""` / `|| ""` fallbacks --
    that's exactly the pattern that let `a.summary.replace(...)` slip
    through uncaught in the first place."""
    body = client.get("/static/js/app.js").text
    assert "function fmtText(value)" in body
    assert "function fmtDate(value)" in body
    assert "function safeArr(value)" in body
    assert "function safeObj(value)" in body

    portfolio_fn = body.split("async function renderHomePortfolio")[1].split(
        "function renderTodaysFocus"
    )[0]
    mini_card_fn = body.split("function homeProjectMiniCardHtml")[1].split(
        "async function renderHomePortfolio"
    )[0]
    assert "safeArr(" in portfolio_fn
    assert "safeObj(" in portfolio_fn
    assert "fmtText(" in portfolio_fn
    assert "fmtText(" in mini_card_fn


def test_dproject_route_registered():
    body = client.get("/static/js/app.js").text
    assert "dproject: renderDiscoveredProjectDetail" in body


def test_discovered_project_detail_has_required_sections():
    body = client.get("/static/js/app.js").text
    for section_fn in (
        "dprojectOverviewHtml",
        "dprojectGitHtml",
        "dprojectDocumentationHtml",
        "dprojectChildrenHtml",
        "dprojectAssetsHtml",
        "dprojectTestsHtml",
        "dprojectAiSessionsHtml",
        "dprojectLatestSnapshotHtml",
        "dprojectNextActionHtml",
        "dprojectRisksHtml",
    ):
        assert section_fn in body
    assert "NOT_YET_DEFINED" in body
    assert "Not yet defined" in body


def test_projects_page_shows_all_required_discovered_fields():
    body = client.get("/static/js/app.js").text
    assert "discoveredProjectCardHtml" in body
    for field in (
        "git_is_repo",
        "git_is_dirty",
        "git_last_commit_date",
        "documentation_status",
        "test_status",
        "asset_count",
        "repository_count",
        "component_count",
        "next_action",
    ):
        assert field in body
    assert 'fetchJSON("/workspace/discovered?view=top_level")' in body


def test_advisor_page_has_discovered_projects_section():
    body = client.get("/static/js/app.js").text
    assert "renderAdvisorDiscoveredRecs" in body
    assert '"/workspace/advisor"' in body
    assert "discoveredRecommendationCardHtml" in body
    assert "Discovered Projects" in body


def test_assets_page_wired_to_real_discovery_index():
    """Sprint C4 (Assets OS): the Assets page moved from the flat
    Sprint 4 `/workspace/assets` listing to the canonical `GET /assets`
    gallery/search endpoint (`app.assets.service`) -- still real,
    discovery-indexed data, now with duplicate grouping/reusable flags
    computed the same deterministic way, just served through the richer
    canonical surface instead of the legacy endpoint directly."""
    body = client.get("/static/js/app.js").text
    assert "/assets?" in body
    assert "assetCardHtml" in body
    assert "duplicate_group_id" in body
    assert "reusable" in body
    # Must no longer depend on the old graph-based placeholder.
    assert 'fetchJSON("/graph?node_type=Asset")' not in body


def test_stale_data_warning_present_on_workspace_page():
    body = client.get("/static/js/app.js").text
    assert "is_stale" in body
    assert "Stale" in body
