"""Unit tests for the modular Health Score engine (app.projects.health)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.projects.health import compute_health_score
from app.projects.health.activity import score_recent_activity
from app.projects.health.commits import score_recent_commits
from app.projects.health.conversations import score_recent_conversations
from app.projects.health.decisions import score_unresolved_decisions
from app.projects.health.deliverables import score_missing_deliverables
from app.projects.health.todos import score_open_todos

NOW = datetime(2026, 1, 15, tzinfo=timezone.utc)


def iso(days_ago: int) -> str:
    return (NOW - timedelta(days=days_ago)).isoformat()


def test_score_recent_activity_decays_with_age():
    assert score_recent_activity(iso(0), now=NOW) == 100
    assert score_recent_activity(iso(5), now=NOW) == 85
    assert score_recent_activity(iso(20), now=NOW) == 65
    assert score_recent_activity(iso(60), now=NOW) == 35
    assert score_recent_activity(iso(365), now=NOW) == 5


def test_score_recent_activity_handles_missing_or_bad_input():
    assert score_recent_activity(None) == 0
    assert score_recent_activity("not-a-date") == 0


def test_score_open_todos_scales_with_open_count():
    assert score_open_todos([]) == 100
    assert score_open_todos([{"status": "done"}, {"status": "done"}]) == 100
    assert score_open_todos([{"status": "open"}]) == 80
    assert score_open_todos([{"status": "open"}] * 5) == 60
    assert score_open_todos([{"status": "open"}] * 8) == 35
    assert score_open_todos([{"status": "open"}] * 20) == 15


def test_score_unresolved_decisions_scales_with_pending_count():
    assert score_unresolved_decisions([]) == 100
    assert score_unresolved_decisions([{"status": "resolved"}]) == 100
    assert score_unresolved_decisions([{"status": "pending"}]) == 75
    assert score_unresolved_decisions([{"status": "pending"}] * 3) == 50
    assert score_unresolved_decisions([{"status": "pending"}] * 10) == 20


def test_score_missing_deliverables_uses_delivered_ratio():
    assert score_missing_deliverables([]) == 70
    assert score_missing_deliverables([{"status": "delivered"}]) == 100
    assert score_missing_deliverables([{"status": "planned"}]) == 0
    assert score_missing_deliverables([{"status": "delivered"}, {"status": "planned"}]) == 50


def test_score_recent_conversations_uses_most_recent_date():
    assert score_recent_conversations([], now=NOW) == 30
    assert score_recent_conversations([iso(2)], now=NOW) == 100
    assert score_recent_conversations([iso(20)], now=NOW) == 75
    assert score_recent_conversations([iso(60)], now=NOW) == 45
    assert score_recent_conversations([iso(200)], now=NOW) == 20


def test_score_recent_commits_returns_none_when_unavailable():
    assert score_recent_commits(None) is None


def test_score_recent_commits_scores_when_available():
    assert score_recent_commits([], now=NOW) == 30
    assert score_recent_commits([iso(0)], now=NOW) == 100
    assert score_recent_commits([iso(5)], now=NOW) == 80
    assert score_recent_commits([iso(20)], now=NOW) == 55
    assert score_recent_commits([iso(60)], now=NOW) == 25


def test_compute_health_score_excludes_commits_when_unavailable():
    # compute_health_score() uses real "now" internally (it doesn't accept a
    # `now` override), so use the actual current time here rather than the
    # fixed NOW used for the per-signal unit tests above.
    right_now = datetime.now(timezone.utc).isoformat()
    project = {"updated_at": right_now, "todos": [], "decisions": [], "deliverables": []}
    result = compute_health_score(project, conversation_dates=[])
    assert "recent_commits" not in result["breakdown"]
    # activity=100, todos=100, decisions=100, deliverables=70 (no deliverables tracked),
    # conversations=30 (none linked) -> weighted average, renormalized over 5 signals.
    assert result["score"] == 83


def test_compute_health_score_includes_commits_when_available():
    project = {"updated_at": iso(0), "todos": [], "decisions": [], "deliverables": []}
    result = compute_health_score(project, conversation_dates=[], commit_dates=[iso(0)])
    assert "recent_commits" in result["breakdown"]


def test_compute_health_score_is_bounded_0_to_100():
    empty_project = {}
    result = compute_health_score(empty_project)
    assert 0 <= result["score"] <= 100


def test_compute_health_score_degrades_for_unhealthy_project():
    project = {
        "updated_at": iso(400),
        "todos": [{"status": "open"}] * 20,
        "decisions": [{"status": "pending"}] * 10,
        "deliverables": [{"status": "planned"}] * 5,
    }
    result = compute_health_score(project, conversation_dates=[iso(400)])
    assert result["score"] < 30
