"""Tests for Workspace Advisor 2.0's rule-based recommendations (Sprint 4
§5): each rule fires only with real supporting evidence, and never as
generic filler.
"""

from __future__ import annotations

from app.workspace import advisor


def _item(**overrides):
    base = {
        "id": "abc123",
        "name": "my-app",
        "adopted": True,
        "business_value": "medium",
        "move_risk": "low",
        "health_score": 50,
        "asset_count": 0,
        "next_action": {"text": None, "source": "none", "confidence": 0.0},
        "discovery_detail": {
            "has_readme": True,
            "has_roadmap": True,
            "has_changelog": False,
            "has_tests": True,
            "commercial_readiness": "early",
            "maturity": "active",
            "move_risk_reasons": [],
            "git": {"is_repo": True, "is_dirty": False, "last_commit_date": None, "branch": "main"},
        },
        "last_modified": None,
    }
    base.update(overrides)
    return base


def test_inactive_rule_fires_with_real_evidence():
    item = _item(discovery_detail={**_item()["discovery_detail"], "git": {"is_repo": False}})
    item["last_modified"] = "2020-01-01T00:00:00+00:00"
    result = advisor.rule_inactive(item)
    assert result is not None
    assert "days" in result["reason"]
    assert result["evidence"]


def test_inactive_rule_does_not_fire_when_recent():
    item = _item()
    from datetime import datetime, timezone

    item["last_modified"] = datetime.now(timezone.utc).isoformat()
    assert advisor.rule_inactive(item) is None


def test_dirty_git_tree_fires_only_when_dirty():
    clean = _item()
    assert advisor.rule_dirty_git_tree(clean) is None

    dirty = _item(
        discovery_detail={
            **_item()["discovery_detail"],
            "git": {"is_repo": True, "is_dirty": True, "branch": "main"},
        }
    )
    result = advisor.rule_dirty_git_tree(dirty)
    assert result is not None
    assert "uncommitted" in result["reason"].lower()


def test_no_readme_fires_only_when_missing():
    has_readme = _item()
    assert advisor.rule_no_readme(has_readme) is None

    no_readme = _item(discovery_detail={**_item()["discovery_detail"], "has_readme": False})
    result = advisor.rule_no_readme(no_readme)
    assert result is not None
    assert result["evidence"] == ["has_readme = false"]


def test_no_roadmap_requires_both_roadmap_and_changelog_missing():
    has_roadmap = _item()
    assert advisor.rule_no_roadmap(has_roadmap) is None

    neither = _item(
        discovery_detail={
            **_item()["discovery_detail"],
            "has_roadmap": False,
            "has_changelog": False,
        }
    )
    assert advisor.rule_no_roadmap(neither) is not None


def test_no_tests_fires_only_for_top_level_projects_without_tests():
    has_tests = _item()
    assert advisor.rule_no_tests(has_tests) is None

    no_tests_not_project = _item(
        discovery_detail={**_item()["discovery_detail"], "has_tests": False}, item_kind="component"
    )
    assert advisor.rule_no_tests(no_tests_not_project) is None

    no_tests_project = _item(
        discovery_detail={**_item()["discovery_detail"], "has_tests": False}, item_kind="project"
    )
    result = advisor.rule_no_tests(no_tests_project)
    assert result is not None


def test_next_action_available_includes_real_source_and_confidence():
    item = _item(next_action={"text": "Ship the feature", "source": "TODO.md", "confidence": 0.75})
    result = advisor.rule_next_action_available(item)
    assert result is not None
    assert "Ship the feature" in result["recommendation"]
    assert result["confidence"] == 0.75


def test_next_action_absent_produces_no_recommendation():
    item = _item(next_action={"text": None, "source": "none", "confidence": 0.0})
    assert advisor.rule_next_action_available(item) is None


def test_high_value_low_activity_requires_both_conditions():
    from datetime import datetime, timedelta, timezone

    old = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()

    high_value_active = _item(
        business_value="high", last_modified=datetime.now(timezone.utc).isoformat()
    )
    assert advisor.rule_high_value_low_activity(high_value_active) is None

    medium_value_inactive = _item(business_value="medium", last_modified=old)
    assert advisor.rule_high_value_low_activity(medium_value_inactive) is None

    high_value_inactive = _item(business_value="high", last_modified=old)
    result = advisor.rule_high_value_low_activity(high_value_inactive)
    assert result is not None
    assert "high" in result["evidence"][0]


def test_high_move_risk_includes_real_reasons():
    item = _item(
        move_risk="high",
        discovery_detail={
            **_item()["discovery_detail"],
            "move_risk_reasons": ["27 hardcoded absolute-path references found"],
        },
    )
    result = advisor.rule_high_move_risk(item)
    assert result is not None
    assert result["evidence"] == ["27 hardcoded absolute-path references found"]


def test_high_move_risk_absent_for_low_risk():
    assert advisor.rule_high_move_risk(_item(move_risk="low")) is None


def test_momentum_requires_recent_activity_and_next_action():
    from datetime import datetime, timezone

    recent = datetime.now(timezone.utc).isoformat()
    with_next_action = _item(
        last_modified=recent,
        next_action={"text": "keep going", "source": "TODO.md", "confidence": 0.7},
    )
    assert advisor.rule_momentum(with_next_action) is not None

    without_next_action = _item(
        last_modified=recent, next_action={"text": None, "source": "none", "confidence": 0.0}
    )
    assert advisor.rule_momentum(without_next_action) is None


def test_assets_no_commercial_output_requires_threshold_and_readiness():
    few_assets = _item(
        asset_count=3,
        discovery_detail={**_item()["discovery_detail"], "commercial_readiness": "not-commercial"},
    )
    assert advisor.rule_assets_no_commercial_output(few_assets) is None

    many_assets_commercial = _item(
        asset_count=15,
        discovery_detail={**_item()["discovery_detail"], "commercial_readiness": "production"},
    )
    assert advisor.rule_assets_no_commercial_output(many_assets_commercial) is None

    many_assets_not_commercial = _item(
        asset_count=15,
        discovery_detail={**_item()["discovery_detail"], "commercial_readiness": "not-commercial"},
    )
    result = advisor.rule_assets_no_commercial_output(many_assets_not_commercial)
    assert result is not None
    assert "15" in result["reason"]


def test_near_completion_requires_health_readiness_and_not_stale():
    low_health = _item(
        health_score=50,
        discovery_detail={**_item()["discovery_detail"], "commercial_readiness": "client-ready"},
    )
    assert advisor.rule_near_completion(low_health) is None

    stale = _item(
        health_score=90,
        discovery_detail={
            **_item()["discovery_detail"],
            "commercial_readiness": "client-ready",
            "maturity": "stale",
        },
    )
    assert advisor.rule_near_completion(stale) is None

    good = _item(
        health_score=85,
        discovery_detail={
            **_item()["discovery_detail"],
            "commercial_readiness": "production",
            "maturity": "active",
        },
    )
    result = advisor.rule_near_completion(good)
    assert result is not None


def test_generate_recommendations_sorts_by_priority_and_includes_required_fields():
    item = _item(
        move_risk="high",
        discovery_detail={
            **_item()["discovery_detail"],
            "has_readme": False,
            "move_risk_reasons": ["reason"],
        },
    )
    recs = advisor.generate_recommendations([item])
    assert len(recs) >= 1
    priorities = [r["priority"] for r in recs]
    assert priorities == sorted(priorities, reverse=True)
    for r in recs:
        for field in (
            "project",
            "project_id",
            "recommendation",
            "reason",
            "evidence",
            "priority",
            "confidence",
            "action_link",
        ):
            assert field in r
        assert r["evidence"], "every recommendation must carry real evidence, never empty filler"


def test_generate_recommendations_empty_for_healthy_project_with_no_issues():
    """A project with everything present and healthy should trigger no
    'problem' rules -- verifying rules don't fire without real evidence."""
    item = _item()  # has_readme, has_roadmap, has_tests all True, low risk, active
    recs = advisor.generate_recommendations([item])
    problem_recs = [r for r in recs if r["recommendation"] not in ("Keep the momentum going",)]
    # No next_action set, so momentum/next-action rules also won't fire.
    assert problem_recs == []
