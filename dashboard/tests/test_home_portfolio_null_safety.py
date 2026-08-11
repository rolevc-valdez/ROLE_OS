"""Regression tests for the Home page "Your Projects" portfolio crash:
`Cannot read properties of undefined (reading 'replace')`, reported live
against the real workspace and reproduced via `GET /workspace/home`.

Root cause: `renderHomePortfolio()` in `app.js` rendered `home.recent_assets`
assuming each item had a `summary` field (the Activity feed's shape,
`app/workspace/activity.py`'s `f"Asset: {filename}"` convention) and called
`.replace(/^Asset: /, "")` on it. The real object is a raw
`assets_index.AssetRecord` dict (`filename`/`project`/`path`/...) which
never has a `summary` key -- `a.summary` was `undefined`, and calling
`.replace()` on it threw. Every prior test passed `recent_assets=[]`, so
`.map()`'s callback was never invoked and the bug was never exercised.

This file covers, at the backend/data-contract level (no JS runtime exists
in this repo -- see `test_workspace_sprint4_ui.py`/`test_home_portfolio_ui.py`
for the frontend-source string-assertion side of this regression):

1. The exact real payload shape captured live against the real workspace
   (`ROLE_KNOWLEDGE_OS`'s actual asset records) passed through
   `build_home_portfolio` unmodified.
2. The full missing-field matrix requested for Home: a project with no
   next action, no technology stack, no git data, no status, no recent
   activity, and explicit `None`/absent optional fields throughout.
"""

from __future__ import annotations

from app.workspace.portfolio import build_home_portfolio

# The exact shape captured live from `GET /workspace/home` against the real
# `1 - IA PROJECTS` workspace (`ROLE_KNOWLEDGE_OS`'s real asset records) --
# this is what `assets_index.AssetRecord` actually produces, and is the
# payload that crashed the old renderer.
REAL_RECENT_ASSETS_PAYLOAD = [
    {
        "filename": "home.png",
        "project": "ROLE_KNOWLEDGE_OS",
        "path": "C:\\Users\\rolev\\My Drive (rolevc@gmail.com)\\1 - IA PROJECTS"
        "\\ROLE_KNOWLEDGE_OS\\ROLE_OS_BUILDER\\home.png",
        "asset_type": "image",
        "category": "image",
        "size_bytes": 202362,
        "modified_at": "2026-07-23T12:30:21.527428+00:00",
        "reusable": False,
        "duplicate_hash": "e2149a4027c77c9ec5f9f39394c250c16c0ab0d9",
    },
    {
        "filename": "shot_4_logo.png",
        "project": "ROLE_KNOWLEDGE_OS",
        "path": "C:\\Users\\rolev\\My Drive (rolevc@gmail.com)\\1 - IA PROJECTS"
        "\\ROLE_KNOWLEDGE_OS\\ROLE_OS_BUILDER\\shot_4_logo.png",
        "asset_type": "image",
        "category": "logo",
        "size_bytes": 88214,
        "modified_at": "2026-07-21T07:00:00.000000+00:00",
        "reusable": True,
        "duplicate_hash": None,
    },
]


def _minimal_item(**overrides) -> dict:
    """A bare-minimum enriched project item -- the shape
    `list_enriched_top_level_projects` guarantees (id/name/adopted always
    set), with everything else deliberately absent or `None` to model a
    real discovered project that has no git history, no tech stack, no
    status, and no next action yet."""
    base = {
        "id": "p1",
        "name": "bare-project",
        "adopted": True,
    }
    base.update(overrides)
    return base


def test_real_captured_recent_assets_payload_does_not_crash_the_backend():
    """The exact response shape that crashed the frontend must still be a
    valid, well-formed backend response -- proving the backend was never
    the bug (§10: don't change backend behavior for a frontend-only
    defect)."""
    home = build_home_portfolio(
        items=[],
        recommendations=[],
        recent_activity=[],
        latest_ai_session=None,
        recent_assets=REAL_RECENT_ASSETS_PAYLOAD,
    )
    assert home["recent_assets"] == REAL_RECENT_ASSETS_PAYLOAD
    for asset in home["recent_assets"]:
        assert "filename" in asset
        assert "summary" not in asset


def test_project_with_no_next_action():
    item = _minimal_item(next_action=None)
    home = build_home_portfolio(
        items=[item],
        recommendations=[],
        recent_activity=[],
        latest_ai_session=None,
        recent_assets=[],
    )
    assert home["suggested_project"] is None
    assert home["quick_resume"] is None


def test_project_with_no_technology_stack():
    """No `discovery_detail.languages`/`tech_markers` at all -- Home's
    portfolio functions never touch tech stack fields, so this must be a
    complete no-op for them."""
    item = _minimal_item(discovery_detail={"git": {"is_repo": False}})
    home = build_home_portfolio(
        items=[item],
        recommendations=[],
        recent_activity=[],
        latest_ai_session=None,
        recent_assets=[],
    )
    assert home["total_projects"] == 1
    assert home["total_adopted"] == 1


def test_project_with_no_git_data():
    item = _minimal_item(discovery_detail={})
    home = build_home_portfolio(
        items=[item],
        recommendations=[],
        recent_activity=[],
        latest_ai_session=None,
        recent_assets=[],
    )
    assert home["last_active_project"] is None or home["last_active_project"]["id"] == "p1"


def test_project_with_no_status_field():
    item = _minimal_item()
    assert "status" not in item
    home = build_home_portfolio(
        items=[item],
        recommendations=[],
        recent_activity=[],
        latest_ai_session=None,
        recent_assets=[],
    )
    assert home["total_projects"] == 1


def test_no_recent_activity():
    home = build_home_portfolio(
        items=[_minimal_item()],
        recommendations=[],
        recent_activity=[],
        latest_ai_session=None,
        recent_assets=[],
    )
    assert home["recent_commits"] == []


def test_null_and_undefined_optional_fields_throughout():
    """A project item missing every optional key entirely (not merely
    `None`), plus explicit `None` for `latest_ai_session` and empty lists
    everywhere else -- the full "nothing is defined yet" case."""
    item = {"id": "p1", "name": "bare-project", "adopted": True}
    home = build_home_portfolio(
        items=[item],
        recommendations=[],
        recent_activity=[],
        latest_ai_session=None,
        recent_assets=[],
    )
    assert home["latest_ai_session"] is None
    assert home["suggested_project"] is None
    assert home["quick_resume"] is None
    assert home["recent_commits"] == []
    assert home["recent_assets"] == []
    assert home["projects_needing_attention"] == []
