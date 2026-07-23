"""Unit tests for every Advisor rule (app.advisor.rules.*).

Each rule is tested in isolation with a synthetic project + RuleContext,
independent of any database — this is what "modular" buys us: each rule
can be verified without spinning up projects/advisor DBs at all.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.advisor.models import RuleContext
from app.advisor.rules import (
    blocked_dependency,
    capability_opportunity,
    critical_health,
    inactive_high_priority,
    missing_deliverables,
    near_completion,
    overdue_todos,
    stale_project,
)

NOW = datetime(2026, 1, 15, tzinfo=timezone.utc)


def iso(days_ago: int) -> str:
    return (NOW - timedelta(days=days_ago)).isoformat()


def base_project(**overrides) -> dict:
    project = {
        "id": "p1",
        "workspace": "Products",
        "name": "Test Project",
        "description": "",
        "status": "active",
        "priority": "medium",
        "tags": [],
        "updated_at": iso(1),
        "todos": [],
        "decisions": [],
        "deliverables": [],
    }
    project.update(overrides)
    return project


def base_context(**overrides) -> RuleContext:
    context = RuleContext(now=NOW)
    for key, value in overrides.items():
        setattr(context, key, value)
    return context


# ---------------------------------------------------------------------------
# stale_project
# ---------------------------------------------------------------------------


def test_stale_project_fires_when_inactive_30_days():
    project = base_project(updated_at=iso(35), priority="low")
    candidates = stale_project.evaluate(project, base_context())
    assert len(candidates) == 1
    assert candidates[0].recommendation_type == "update_stale_project"


def test_stale_project_does_not_fire_when_recent():
    project = base_project(updated_at=iso(5))
    assert stale_project.evaluate(project, base_context()) == []


def test_stale_project_ignores_completed_projects():
    project = base_project(updated_at=iso(90), status="completed")
    assert stale_project.evaluate(project, base_context()) == []


def test_stale_project_ignores_missing_updated_at():
    project = base_project(updated_at=None)
    assert stale_project.evaluate(project, base_context()) == []


# ---------------------------------------------------------------------------
# near_completion
# ---------------------------------------------------------------------------


def test_near_completion_fires_when_almost_done():
    project = base_project(
        deliverables=[{"status": "delivered"}, {"status": "delivered"}, {"status": "planned", "text": "final"}]
    )
    context = base_context(dependents=[{"dependent_project_name": "Brand Character OS"}])
    candidates = near_completion.evaluate(project, context)
    assert len(candidates) == 1
    assert candidates[0].recommendation_type == "continue_project"
    assert "Brand Character OS" in candidates[0].impact


def test_near_completion_does_not_fire_when_far_from_done():
    project = base_project(deliverables=[{"status": "planned"}, {"status": "planned"}, {"status": "delivered"}])
    assert near_completion.evaluate(project, base_context()) == []


def test_near_completion_does_not_fire_with_too_much_remaining():
    deliverables = [{"status": "delivered"}] * 10 + [{"status": "planned"}] * 6
    project = base_project(deliverables=deliverables)
    assert near_completion.evaluate(project, base_context()) == []


def test_near_completion_ignores_completed_projects():
    project = base_project(status="completed", deliverables=[{"status": "delivered"}, {"status": "planned"}])
    assert near_completion.evaluate(project, base_context()) == []


# ---------------------------------------------------------------------------
# blocked_dependency
# ---------------------------------------------------------------------------


def test_blocked_dependency_fires_on_unhealthy_dependency():
    project = base_project()
    context = base_context(
        dependencies=[
            {"depends_on_project_name": "ROLE Master", "depends_on_health_score": 20, "depends_on_status": "active"}
        ]
    )
    candidates = blocked_dependency.evaluate(project, context)
    assert len(candidates) == 1
    assert candidates[0].recommendation_type == "unblock_dependency"
    assert "ROLE Master" in candidates[0].evidence[0]


def test_blocked_dependency_fires_on_at_risk_status_even_if_healthy():
    project = base_project()
    context = base_context(
        dependencies=[
            {"depends_on_project_name": "X", "depends_on_health_score": 90, "depends_on_status": "at_risk"}
        ]
    )
    assert len(blocked_dependency.evaluate(project, context)) == 1


def test_blocked_dependency_does_not_fire_on_healthy_dependency():
    project = base_project()
    context = base_context(
        dependencies=[
            {"depends_on_project_name": "X", "depends_on_health_score": 90, "depends_on_status": "active"}
        ]
    )
    assert blocked_dependency.evaluate(project, context) == []


def test_blocked_dependency_no_dependencies():
    assert blocked_dependency.evaluate(base_project(), base_context()) == []


# ---------------------------------------------------------------------------
# critical_health
# ---------------------------------------------------------------------------


def test_critical_health_does_not_fire_above_threshold():
    context = base_context(health={"score": 60, "breakdown": {"recent_activity": 50}})
    assert critical_health.evaluate(base_project(), context) == []


def test_critical_health_fires_review_risk_when_activity_is_weakest():
    context = base_context(
        health={
            "score": 30,
            "breakdown": {
                "recent_activity": 10,
                "open_todos": 100,
                "unresolved_decisions": 100,
                "missing_deliverables": 70,
                "recent_conversations": 30,
            },
        }
    )
    candidates = critical_health.evaluate(base_project(), context)
    assert len(candidates) == 1
    assert candidates[0].recommendation_type == "review_risk"


def test_critical_health_fires_review_decision_when_decisions_are_weakest():
    context = base_context(
        health={
            "score": 30,
            "breakdown": {
                "recent_activity": 90,
                "open_todos": 100,
                "unresolved_decisions": 15,
                "missing_deliverables": 70,
                "recent_conversations": 60,
            },
        }
    )
    project = base_project(decisions=[{"status": "pending"}, {"status": "pending"}])
    candidates = critical_health.evaluate(project, context)
    assert len(candidates) == 1
    assert candidates[0].recommendation_type == "review_decision"


def test_critical_health_handles_missing_health_context():
    assert critical_health.evaluate(base_project(), base_context(health=None)) == []


# ---------------------------------------------------------------------------
# overdue_todos
# ---------------------------------------------------------------------------


def test_overdue_todos_fires_with_enough_overdue_items():
    project = base_project(
        todos=[
            {"status": "open", "created_at": iso(20), "text": "a"},
            {"status": "open", "created_at": iso(25), "text": "b"},
        ]
    )
    candidates = overdue_todos.evaluate(project, base_context())
    assert len(candidates) == 1
    assert candidates[0].recommendation_type == "resolve_todo"


def test_overdue_todos_does_not_fire_below_minimum_count():
    project = base_project(todos=[{"status": "open", "created_at": iso(20), "text": "a"}])
    assert overdue_todos.evaluate(project, base_context()) == []


def test_overdue_todos_ignores_recent_or_done_todos():
    project = base_project(
        todos=[
            {"status": "open", "created_at": iso(1), "text": "fresh"},
            {"status": "done", "created_at": iso(30), "text": "done already"},
        ]
    )
    assert overdue_todos.evaluate(project, base_context()) == []


# ---------------------------------------------------------------------------
# missing_deliverables
# ---------------------------------------------------------------------------


def test_missing_deliverables_fires_with_pending_items():
    project = base_project(deliverables=[{"status": "delivered"}, {"status": "planned", "text": "x"}])
    candidates = missing_deliverables.evaluate(project, base_context())
    assert len(candidates) == 1
    assert candidates[0].recommendation_type == "finish_deliverable"


def test_missing_deliverables_no_deliverables_tracked():
    assert missing_deliverables.evaluate(base_project(deliverables=[]), base_context()) == []


def test_missing_deliverables_too_many_missing_does_not_fire():
    deliverables = [{"status": "planned"}] * 8
    assert missing_deliverables.evaluate(base_project(deliverables=deliverables), base_context()) == []


def test_missing_deliverables_ignores_inactive_projects():
    project = base_project(status="archived", deliverables=[{"status": "planned"}])
    assert missing_deliverables.evaluate(project, base_context()) == []


# ---------------------------------------------------------------------------
# inactive_high_priority
# ---------------------------------------------------------------------------


def test_inactive_high_priority_fires_for_high_priority_stalled_project():
    project = base_project(priority="high", updated_at=iso(10))
    candidates = inactive_high_priority.evaluate(project, base_context())
    assert len(candidates) == 1
    assert candidates[0].recommendation_type == "review_risk"


def test_inactive_high_priority_ignores_medium_priority():
    project = base_project(priority="medium", updated_at=iso(10))
    assert inactive_high_priority.evaluate(project, base_context()) == []


def test_inactive_high_priority_ignores_recently_active():
    project = base_project(priority="critical", updated_at=iso(1))
    assert inactive_high_priority.evaluate(project, base_context()) == []


# ---------------------------------------------------------------------------
# capability_opportunity
# ---------------------------------------------------------------------------


def test_capability_opportunity_fires_on_tag_match():
    project = base_project(tags=["branding"])
    context = base_context(
        all_capabilities=[
            {"id": "cap1", "project_id": "other", "name": "Brand Identity", "category": "branding", "provider_project_name": "ROLE Master"}
        ]
    )
    candidates = capability_opportunity.evaluate(project, context)
    assert len(candidates) == 1
    assert candidates[0].recommendation_type == "reuse_capability"
    assert candidates[0].confidence_score > 50


def test_capability_opportunity_fires_on_description_keyword_match():
    project = base_project(description="we need a master prompt for this")
    context = base_context(
        all_capabilities=[
            {"id": "cap1", "project_id": "other", "name": "master prompt", "category": "", "provider_project_name": "ROLE Master"}
        ]
    )
    candidates = capability_opportunity.evaluate(project, context)
    assert len(candidates) == 1


def test_capability_opportunity_ignores_own_capabilities():
    project = base_project(tags=["branding"])
    context = base_context(
        all_capabilities=[
            {"id": "cap1", "project_id": "p1", "name": "Brand Identity", "category": "branding", "provider_project_name": "Test Project"}
        ]
    )
    assert capability_opportunity.evaluate(project, context) == []


def test_capability_opportunity_ignores_already_consumed():
    project = base_project(tags=["branding"])
    context = base_context(
        all_capabilities=[
            {"id": "cap1", "project_id": "other", "name": "Brand Identity", "category": "branding", "provider_project_name": "ROLE Master"}
        ],
        capabilities_consumed=[{"id": "cap1"}],
    )
    assert capability_opportunity.evaluate(project, context) == []


def test_capability_opportunity_no_match():
    project = base_project(tags=["unrelated"])
    context = base_context(all_capabilities=[])
    assert capability_opportunity.evaluate(project, context) == []
