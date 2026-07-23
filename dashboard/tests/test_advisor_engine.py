"""Engine-level tests: end-to-end rule evaluation against real Project
Intelligence data, duplicate prevention across regeneration, and the Daily
Brief. Uses isolated projects + advisor SQLite files per test.
"""

from __future__ import annotations

import sqlite3

import pytest

from app.advisor import engine
from app.config import Settings
from app.projects import db as projects_db


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("ROLE_OS_PROJECTS_DB_PATH", str(tmp_path / "projects.db"))
    monkeypatch.setenv("ROLE_OS_ADVISOR_DB_PATH", str(tmp_path / "advisor.db"))
    # Point at a knowledge DB that doesn't exist — the engine must degrade
    # gracefully (empty conversation dates) rather than error out.
    monkeypatch.setenv("ROLE_OS_DB_PATH", str(tmp_path / "does_not_exist.db"))
    return Settings()


def force_updated_at(settings: Settings, project_id: str, iso_value: str) -> None:
    conn = sqlite3.connect(str(settings.projects_db_path))
    conn.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (iso_value, project_id))
    conn.commit()
    conn.close()


def test_refresh_recommendations_generates_from_real_project_data(settings):
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    stale_iso = (now - timedelta(days=45)).isoformat()

    project = projects_db.create_project(name="Old Idea", workspace="Ideas", priority="low", settings=settings)
    force_updated_at(settings, project["id"], stale_iso)

    recs = engine.get_recommendations(settings=settings)
    assert len(recs) == 1
    assert recs[0]["recommendation_type"] == "update_stale_project"
    assert recs[0]["project_id"] == project["id"]


def test_regenerating_does_not_create_duplicates(settings):
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    stale_iso = (now - timedelta(days=45)).isoformat()
    project = projects_db.create_project(name="Old Idea", workspace="Ideas", settings=settings)
    force_updated_at(settings, project["id"], stale_iso)

    first = engine.get_recommendations(settings=settings)
    second = engine.get_recommendations(settings=settings)
    assert len(first) == len(second) == 1
    assert first[0]["id"] == second[0]["id"]


def test_two_rules_producing_same_type_are_merged_not_duplicated(settings):
    """critical_health and inactive_high_priority can both independently
    decide 'review_risk' for the same project — the engine must persist
    only one row for that (project_id, recommendation_type) pair."""
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    project = projects_db.create_project(
        name="Troubled", workspace="Products", priority="critical", settings=settings
    )
    force_updated_at(settings, project["id"], (now - timedelta(days=10)).isoformat())
    # Push health score down: many overdue todos.
    for i in range(6):
        projects_db.add_collection_item(
            project["id"],
            "todos",
            {"text": f"todo {i}", "status": "open", "created_at": (now - timedelta(days=20)).isoformat()},
            settings,
        )

    recs = engine.get_recommendations(settings=settings, recommendation_type="review_risk")
    assert len(recs) <= 1


def test_dismiss_prevents_regeneration_of_same_finding(settings):
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    project = projects_db.create_project(name="Old Idea", workspace="Ideas", settings=settings)
    force_updated_at(settings, project["id"], (now - timedelta(days=45)).isoformat())

    recs = engine.get_recommendations(settings=settings)
    engine.dismiss_recommendation(recs[0]["id"], settings)

    still_hidden = engine.get_recommendations(settings=settings)
    assert still_hidden == []

    with_dismissed = engine.get_recommendations(settings=settings, include_dismissed=True)
    assert len(with_dismissed) == 1
    assert with_dismissed[0]["dismissed"] is True


def test_complete_persists_across_regeneration(settings):
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    project = projects_db.create_project(name="Old Idea", workspace="Ideas", settings=settings)
    force_updated_at(settings, project["id"], (now - timedelta(days=45)).isoformat())

    recs = engine.get_recommendations(settings=settings)
    engine.complete_recommendation(recs[0]["id"], settings)

    rec = engine.get_recommendation(recs[0]["id"], settings)
    assert rec["completed"] is True


def test_workspace_filter_scopes_generation(settings):
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    p1 = projects_db.create_project(name="A", workspace="Products", settings=settings)
    p2 = projects_db.create_project(name="B", workspace="Ideas", settings=settings)
    force_updated_at(settings, p1["id"], (now - timedelta(days=45)).isoformat())
    force_updated_at(settings, p2["id"], (now - timedelta(days=45)).isoformat())

    recs = engine.get_recommendations(workspace="Products", settings=settings)
    assert {r["project_id"] for r in recs} == {p1["id"]}


def test_daily_brief_structure(settings):
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    project = projects_db.create_project(name="Old Idea", workspace="Ideas", priority="high", settings=settings)
    force_updated_at(settings, project["id"], (now - timedelta(days=45)).isoformat())

    brief = engine.generate_daily_brief(settings=settings)
    assert "Good morning" in brief["greeting"]
    assert isinstance(brief["top_recommended_projects"], list)
    assert isinstance(brief["stale_high_priority"], list)
    assert brief["generated_at"]


def test_daily_brief_excludes_dismissed_recommendations(settings):
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    project = projects_db.create_project(name="Old Idea", workspace="Ideas", settings=settings)
    force_updated_at(settings, project["id"], (now - timedelta(days=45)).isoformat())

    recs = engine.get_recommendations(settings=settings)
    engine.dismiss_recommendation(recs[0]["id"], settings)

    brief = engine.generate_daily_brief(settings=settings)
    all_ids = [
        item["recommendation_id"]
        for section in (
            "top_recommended_projects",
            "critical_risks",
            "blocked_projects",
            "near_completion",
            "stale_high_priority",
            "capability_opportunities",
        )
        for item in brief[section]
    ]
    assert recs[0]["id"] not in all_ids


def test_engine_degrades_gracefully_with_no_projects(settings):
    assert engine.get_recommendations(settings=settings) == []
    brief = engine.generate_daily_brief(settings=settings)
    assert brief["top_recommended_projects"] == []
