"""Unit tests for the shared Advisor scoring toolkit (app.advisor.scoring)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.advisor.scoring import (
    clamp,
    completion_ratio,
    confidence_from_availability,
    days_since,
    effort_from_count,
    priority_weight,
    staleness_score,
    weighted_combine,
)

NOW = datetime(2026, 1, 15, tzinfo=timezone.utc)


def iso(days_ago: int) -> str:
    return (NOW - timedelta(days=days_ago)).isoformat()


def test_priority_weight_known_and_unknown():
    assert priority_weight("low") == 25
    assert priority_weight("medium") == 50
    assert priority_weight("high") == 75
    assert priority_weight("critical") == 100
    assert priority_weight(None) == 50
    assert priority_weight("nonsense") == 50


def test_days_since_computes_and_handles_bad_input():
    assert days_since(iso(5), now=NOW) == 5
    assert days_since(None) is None
    assert days_since("not-a-date") is None


def test_clamp_bounds_values():
    assert clamp(150) == 100
    assert clamp(-10) == 0
    assert clamp(50.4) == 50


def test_weighted_combine_renormalizes_over_present_signals():
    # Only one signal present: its weight becomes 100% regardless of its
    # configured weight relative to a missing sibling.
    result = weighted_combine({"a": 80}, {"a": 0.3, "b": 0.7})
    assert result == 80


def test_weighted_combine_empty_signals_returns_zero():
    assert weighted_combine({}, {"a": 1.0}) == 0


def test_confidence_from_availability_scales_with_ratio():
    assert confidence_from_availability([True, True, True]) == 100
    assert confidence_from_availability([False, False, False]) == 40  # floor
    assert confidence_from_availability([]) == 40


def test_staleness_score_thresholds():
    assert staleness_score(None) == 0
    assert staleness_score(3, mild=7, severe=30) == 0
    assert staleness_score(30, mild=7, severe=30) == 100
    assert 0 < staleness_score(15, mild=7, severe=30) < 100


def test_completion_ratio():
    assert completion_ratio(0, 0) is None
    assert completion_ratio(1, 2) == 0.5
    assert completion_ratio(2, 2) == 1.0


def test_effort_from_count_thresholds():
    assert effort_from_count(1) == "small"
    assert effort_from_count(2) == "small"
    assert effort_from_count(3) == "medium"
    assert effort_from_count(5) == "medium"
    assert effort_from_count(6) == "large"
