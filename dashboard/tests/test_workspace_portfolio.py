"""Tests for Home page portfolio aggregation (Sprint 4 §4)."""

from __future__ import annotations

from app.workspace.portfolio import (
    build_home_portfolio,
    last_active_project,
    most_recently_modified_project,
    suggested_project_to_continue,
)


def _item(**overrides):
    base = {
        "id": "p1",
        "name": "my-app",
        "adopted": True,
        "business_value": "medium",
        "last_modified": "2026-01-01T00:00:00+00:00",
        "next_action": {"text": None, "source": "none", "confidence": 0.0},
        "discovery_detail": {"git": {"is_repo": False}},
    }
    base.update(overrides)
    return base


def test_last_active_project_picks_most_recent_activity():
    old = _item(id="old", last_modified="2020-01-01T00:00:00+00:00")
    from datetime import datetime, timezone

    recent = _item(id="recent", last_modified=datetime.now(timezone.utc).isoformat())
    result = last_active_project([old, recent])
    assert result["id"] == "recent"


def test_last_active_project_none_when_no_activity_data():
    item = _item(last_modified=None, discovery_detail={"git": {"is_repo": False}})
    assert last_active_project([item]) is None


def test_most_recently_modified_project():
    a = _item(id="a", last_modified="2026-01-01T00:00:00+00:00")
    b = _item(id="b", last_modified="2026-06-01T00:00:00+00:00")
    result = most_recently_modified_project([a, b])
    assert result["id"] == "b"


def test_suggested_project_requires_adoption_and_next_action():
    not_adopted = _item(
        adopted=False, next_action={"text": "do X", "source": "TODO.md", "confidence": 0.7}
    )
    assert suggested_project_to_continue([not_adopted]) is None

    no_next_action = _item(
        adopted=True, next_action={"text": None, "source": "none", "confidence": 0.0}
    )
    assert suggested_project_to_continue([no_next_action]) is None

    good = _item(adopted=True, next_action={"text": "do X", "source": "TODO.md", "confidence": 0.7})
    result = suggested_project_to_continue([good])
    assert result is not None
    assert result["project"]["id"] == "p1"
    assert result["reasons"]


def test_suggested_project_prefers_higher_business_value():
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    low_value = _item(
        id="low",
        business_value="low",
        last_modified=now,
        next_action={"text": "a", "source": "TODO.md", "confidence": 0.5},
    )
    high_value = _item(
        id="high",
        business_value="high",
        last_modified=now,
        next_action={"text": "b", "source": "TODO.md", "confidence": 0.5},
    )
    result = suggested_project_to_continue([low_value, high_value])
    assert result["project"]["id"] == "high"


def test_build_home_portfolio_shape_and_quick_resume():
    item = _item(next_action={"text": "Ship it", "source": "TODO.md", "confidence": 0.7})
    home = build_home_portfolio(
        items=[item],
        recommendations=[
            {
                "project": "my-app",
                "project_id": "p1",
                "recommendation": "r",
                "reason": "x",
                "evidence": ["e"],
                "priority": 50,
                "confidence": 0.5,
                "action_link": "#/dproject/p1",
            }
        ],
        recent_activity=[
            {
                "type": "git_commit",
                "timestamp": "2026-01-01T00:00:00+00:00",
                "project_id": "p1",
                "project_name": "my-app",
                "summary": "s",
            }
        ],
        latest_ai_session=None,
        recent_assets=[],
    )
    for key in (
        "last_active_project",
        "most_recently_modified_project",
        "projects_needing_attention",
        "recent_commits",
        "recent_assets",
        "latest_ai_session",
        "suggested_project",
        "quick_resume",
        "total_projects",
        "total_adopted",
    ):
        assert key in home
    assert home["quick_resume"]["action_text"] == "Ship it"
    assert home["quick_resume"]["item_id"] == "p1"
    assert home["total_projects"] == 1
    assert home["total_adopted"] == 1


def test_projects_needing_attention_dedupes_by_project():
    recs = [
        {
            "project": "a",
            "project_id": "p1",
            "recommendation": "r1",
            "reason": "x",
            "evidence": ["e"],
            "priority": 90,
            "confidence": 0.5,
            "action_link": "#",
        },
        {
            "project": "a",
            "project_id": "p1",
            "recommendation": "r2",
            "reason": "y",
            "evidence": ["e"],
            "priority": 80,
            "confidence": 0.5,
            "action_link": "#",
        },
        {
            "project": "b",
            "project_id": "p2",
            "recommendation": "r3",
            "reason": "z",
            "evidence": ["e"],
            "priority": 70,
            "confidence": 0.5,
            "action_link": "#",
        },
    ]
    home = build_home_portfolio(
        items=[], recommendations=recs, recent_activity=[], latest_ai_session=None, recent_assets=[]
    )
    ids = [r["project_id"] for r in home["projects_needing_attention"]]
    assert ids == ["p1", "p2"]


def test_recent_assets_preserves_real_asset_record_shape():
    """Regression: `home.recent_assets` items are raw asset records from
    `assets_index.AssetRecord` (filename/project/path/asset_type/category/
    size_bytes/modified_at/reusable/duplicate_hash) -- they never have a
    `summary` field. The frontend previously assumed the activity-feed
    shape (`summary`, prefixed "Asset: ") instead, causing
    `a.summary.replace(...)` to throw `Cannot read properties of
    undefined (reading 'replace')` on Home whenever any real asset
    existed (every prior test passed `recent_assets=[]`, so this was
    never exercised)."""
    asset = {
        "filename": "logo.png",
        "project": "my-app",
        "path": "/abs/path/logo.png",
        "asset_type": "image",
        "category": "logo",
        "size_bytes": 1024,
        "modified_at": "2026-01-01T00:00:00+00:00",
        "reusable": True,
        "duplicate_hash": None,
    }
    home = build_home_portfolio(
        items=[],
        recommendations=[],
        recent_activity=[],
        latest_ai_session=None,
        recent_assets=[asset],
    )
    assert home["recent_assets"] == [asset]
    assert "filename" in home["recent_assets"][0]
    assert "summary" not in home["recent_assets"][0]
