"""Persistence and duplicate-prevention tests for app.advisor.db.

Each test gets its own isolated SQLite file via a temporary
ROLE_OS_ADVISOR_DB_PATH, mirroring test_projects_db.py.
"""

from __future__ import annotations

import pytest

from app.advisor import db
from app.advisor.models import RecommendationCandidate
from app.config import Settings


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("ROLE_OS_ADVISOR_DB_PATH", str(tmp_path / "advisor.db"))
    return Settings()


def make_candidate(**overrides) -> RecommendationCandidate:
    defaults = dict(
        project_id="p1",
        workspace="Products",
        title="Finish deliverables",
        summary="2 deliverables remaining",
        recommendation_type="finish_deliverable",
        priority_score=80,
        confidence_score=90,
        reason="close to completion",
        evidence=["2 missing deliverables"],
        suggested_action="Finish them",
        estimated_effort="small",
        impact="unblocks X",
        ttl_days=7,
    )
    defaults.update(overrides)
    return RecommendationCandidate(**defaults)


def test_insert_and_get_recommendation(settings):
    rec = db.insert_recommendation(make_candidate(), settings)
    assert rec["project_id"] == "p1"
    assert rec["evidence"] == ["2 missing deliverables"]
    assert rec["dismissed"] is False
    assert rec["completed"] is False

    fetched = db.get_recommendation(rec["id"], settings)
    assert fetched == rec


def test_get_recommendation_returns_none_when_missing(settings):
    assert db.get_recommendation("does-not-exist", settings) is None


def test_find_live_by_dedupe_key(settings):
    candidate = make_candidate()
    assert db.find_live_by_dedupe_key(candidate.dedupe_key(), settings) is None

    rec = db.insert_recommendation(candidate, settings)
    found = db.find_live_by_dedupe_key(candidate.dedupe_key(), settings)
    assert found["id"] == rec["id"]


def test_find_live_by_dedupe_key_ignores_expired(settings):
    candidate = make_candidate(ttl_days=-1)  # already expired at insert time
    db.insert_recommendation(candidate, settings)
    assert db.find_live_by_dedupe_key(candidate.dedupe_key(), settings) is None


def test_dismiss_and_complete_persist(settings):
    rec = db.insert_recommendation(make_candidate(), settings)

    dismissed = db.dismiss_recommendation(rec["id"], settings)
    assert dismissed["dismissed"] is True
    assert db.get_recommendation(rec["id"], settings)["dismissed"] is True

    completed = db.complete_recommendation(rec["id"], settings)
    assert completed["completed"] is True
    assert db.get_recommendation(rec["id"], settings)["completed"] is True


def test_dismiss_returns_none_when_missing(settings):
    assert db.dismiss_recommendation("nope", settings) is None


def test_complete_returns_none_when_missing(settings):
    assert db.complete_recommendation("nope", settings) is None


def test_dismissed_recommendation_still_counts_as_live(settings):
    """A dismissed-but-unexpired recommendation must still block a duplicate
    insert for the same dedupe key — that's what makes dismissal 'stick'."""
    candidate = make_candidate()
    rec = db.insert_recommendation(candidate, settings)
    db.dismiss_recommendation(rec["id"], settings)

    still_live = db.find_live_by_dedupe_key(candidate.dedupe_key(), settings)
    assert still_live is not None
    assert still_live["id"] == rec["id"]


def test_list_recommendations_excludes_dismissed_and_completed_by_default(settings):
    a = db.insert_recommendation(make_candidate(project_id="a"), settings)
    b = db.insert_recommendation(make_candidate(project_id="b"), settings)
    db.dismiss_recommendation(a["id"], settings)
    db.complete_recommendation(b["id"], settings)

    assert db.list_recommendations(settings=settings) == []
    assert len(db.list_recommendations(include_dismissed=True, settings=settings)) == 1
    assert len(db.list_recommendations(include_completed=True, settings=settings)) == 1
    assert len(db.list_recommendations(include_dismissed=True, include_completed=True, settings=settings)) == 2


def test_list_recommendations_filters(settings):
    db.insert_recommendation(
        make_candidate(project_id="a", workspace="Products", recommendation_type="finish_deliverable", priority_score=80),
        settings,
    )
    db.insert_recommendation(
        make_candidate(project_id="b", workspace="Ideas", recommendation_type="resolve_todo", priority_score=30),
        settings,
    )

    assert {r["project_id"] for r in db.list_recommendations(workspace="Products", settings=settings)} == {"a"}
    assert {r["project_id"] for r in db.list_recommendations(project_id="b", settings=settings)} == {"b"}
    assert {r["project_id"] for r in db.list_recommendations(recommendation_type="resolve_todo", settings=settings)} == {"b"}
    assert {r["project_id"] for r in db.list_recommendations(minimum_priority_score=50, settings=settings)} == {"a"}


def test_list_recommendations_sorted_by_priority_desc(settings):
    db.insert_recommendation(make_candidate(project_id="low", priority_score=20), settings)
    db.insert_recommendation(make_candidate(project_id="high", priority_score=90), settings)

    results = db.list_recommendations(settings=settings)
    assert [r["project_id"] for r in results] == ["high", "low"]
