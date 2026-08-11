"""Workspace Advisor 2.0: rule-based recommendations over real discovered/
adopted project evidence (Sprint 4 §5).

A sibling to `app.advisor` (Epic 2's Project Intelligence advisor), not a
rewrite of it -- that engine reasons over manually-entered Project data
(TODOs, deliverables, decisions) with no filesystem/git knowledge at all;
this one reasons over exactly the opposite (git status, README/roadmap/
test presence, move risk, next-action availability) which only exists for
discovered/adopted projects. Every rule is a pure function over one
already-enriched Workspace item (`service.list_enriched_top_level_
projects()`'s output) and either returns nothing or a recommendation
carrying the specific evidence behind it -- never generic filler, per the
brief's explicit requirement.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

INACTIVE_DAYS_THRESHOLD = 90
HIGH_VALUE_INACTIVE_DAYS_THRESHOLD = 60
MOMENTUM_DAYS_THRESHOLD = 7
HEAVY_ASSET_THRESHOLD = 10
NEAR_COMPLETION_HEALTH_THRESHOLD = 80


def _age_days(iso_ts: str | None) -> float | None:
    if not iso_ts:
        return None
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0
    except ValueError:
        return None


def last_activity_age_days(item: dict[str, Any]) -> float | None:
    detail = item.get("discovery_detail") or {}
    git = detail.get("git") or {}
    age = _age_days(git.get("last_commit_date")) if git.get("is_repo") else None
    if age is None:
        age = _age_days(item.get("last_modified"))
    return age


def _action_link(item: dict[str, Any]) -> str:
    return f"#/dproject/{item['id']}"


def _base(
    item: dict[str, Any],
    recommendation: str,
    reason: str,
    evidence: list[str],
    priority: int,
    confidence: float,
) -> dict[str, Any]:
    return {
        "project": item["name"],
        "project_id": item["id"],
        # Sprint 5 §5: every recommendation links directly to Resume Work.
        # `item_id` is what the Resume Work API call needs (kept alongside
        # `project_id` above for backward compatibility with anything
        # already reading that field); `canonical_project_id` is the real
        # ROLE OS Project identity this item resolves to, if adopted.
        "item_id": item["id"],
        "canonical_project_id": item.get("canonical_project_id"),
        "recommendation": recommendation,
        "reason": reason,
        "evidence": evidence,
        "priority": max(0, min(100, priority)),
        "confidence": round(max(0.0, min(1.0, confidence)), 2),
        "action_link": _action_link(item),
    }


def rule_inactive(item: dict[str, Any]) -> dict[str, Any] | None:
    age = last_activity_age_days(item)
    if age is None or age <= INACTIVE_DAYS_THRESHOLD:
        return None
    return _base(
        item,
        "Review for continued relevance",
        f"No activity in {int(age)} days",
        [f"last modified/commit {int(age)} days ago"],
        priority=min(90, 40 + int(age) // 10),
        confidence=0.9,
    )


def rule_dirty_git_tree(item: dict[str, Any]) -> dict[str, Any] | None:
    detail = item.get("discovery_detail") or {}
    git = detail.get("git") or {}
    if not git.get("is_dirty"):
        return None
    return _base(
        item,
        "Commit or stash uncommitted changes",
        "Working tree has uncommitted changes",
        [f"git status shows a dirty working tree on branch '{git.get('branch') or '?'}'"],
        priority=55,
        confidence=1.0,
    )


def rule_no_readme(item: dict[str, Any]) -> dict[str, Any] | None:
    detail = item.get("discovery_detail") or {}
    if detail.get("has_readme"):
        return None
    return _base(
        item,
        "Add a README",
        "No README found in the project root",
        ["has_readme = false"],
        priority=35,
        confidence=1.0,
    )


def rule_no_roadmap(item: dict[str, Any]) -> dict[str, Any] | None:
    detail = item.get("discovery_detail") or {}
    if detail.get("has_roadmap") or detail.get("has_changelog"):
        return None
    return _base(
        item,
        "Add a ROADMAP or CHANGELOG",
        "No roadmap or changelog found",
        ["has_roadmap = false", "has_changelog = false"],
        priority=25,
        confidence=1.0,
    )


def rule_no_tests(item: dict[str, Any]) -> dict[str, Any] | None:
    detail = item.get("discovery_detail") or {}
    if detail.get("has_tests"):
        return None
    if item.get("item_kind") not in ("project",):
        return None
    return _base(
        item,
        "Add tests",
        "No tests detected",
        ["has_tests = false"],
        priority=30,
        confidence=0.85,
    )


def rule_next_action_available(item: dict[str, Any]) -> dict[str, Any] | None:
    next_action = item.get("next_action") or {}
    text = next_action.get("text")
    if not text:
        return None
    return _base(
        item,
        f"Continue: {text}",
        f"A next action was found ({next_action.get('source')})",
        [f"source: {next_action.get('source')}", f"confidence: {next_action.get('confidence')}"],
        priority=40,
        confidence=float(next_action.get("confidence") or 0.3),
    )


def rule_high_value_low_activity(item: dict[str, Any]) -> dict[str, Any] | None:
    age = last_activity_age_days(item)
    if age is None or age < HIGH_VALUE_INACTIVE_DAYS_THRESHOLD:
        return None
    if item.get("business_value") not in ("high", "critical"):
        return None
    return _base(
        item,
        "Re-prioritize or explicitly deprioritize",
        f"High business value but inactive for {int(age)} days",
        [f"business_value = {item.get('business_value')}", f"{int(age)} days since last activity"],
        priority=75,
        confidence=0.85,
    )


def rule_high_move_risk(item: dict[str, Any]) -> dict[str, Any] | None:
    if item.get("move_risk") != "high":
        return None
    detail = item.get("discovery_detail") or {}
    reasons = detail.get("move_risk_reasons") or []
    return _base(
        item,
        "Fix hardcoded paths/config before relocating",
        "Move risk is high",
        list(reasons) or ["move_risk = high"],
        priority=60,
        confidence=0.9,
    )


def rule_momentum(item: dict[str, Any]) -> dict[str, Any] | None:
    age = last_activity_age_days(item)
    next_action = item.get("next_action") or {}
    if age is None or age > MOMENTUM_DAYS_THRESHOLD or not next_action.get("text"):
        return None
    return _base(
        item,
        "Keep the momentum going",
        f"Active in the last {int(age)} day(s) with an open next action",
        [
            f"last activity {int(age)} day(s) ago",
            f"next action source: {next_action.get('source')}",
        ],
        priority=65,
        confidence=0.8,
    )


def rule_assets_no_commercial_output(item: dict[str, Any]) -> dict[str, Any] | None:
    asset_count = item.get("asset_count") or 0
    if asset_count < HEAVY_ASSET_THRESHOLD:
        return None
    if item.get("discovery_detail", {}).get("commercial_readiness") != "not-commercial":
        return None
    return _base(
        item,
        "Decide on a commercial path for these assets",
        f"{asset_count} asset file(s) found but no commercial output detected",
        [f"asset_count = {asset_count}", "commercial_readiness = not-commercial"],
        priority=35,
        confidence=0.7,
    )


def rule_near_completion(item: dict[str, Any]) -> dict[str, Any] | None:
    health = item.get("health_score")
    detail = item.get("discovery_detail") or {}
    if health is None or health < NEAR_COMPLETION_HEALTH_THRESHOLD:
        return None
    if detail.get("commercial_readiness") not in ("client-ready", "production"):
        return None
    if detail.get("maturity") == "stale":
        return None
    return _base(
        item,
        "Consider shipping/launching",
        f"Health score {health} with commercial readiness '{detail.get('commercial_readiness')}'",
        [
            f"health_score = {health}",
            f"commercial_readiness = {detail.get('commercial_readiness')}",
        ],
        priority=70,
        confidence=0.75,
    )


def rule_snapshot_blocker(item: dict[str, Any]) -> dict[str, Any] | None:
    """Sprint C2 (Dashboard 2.0): "blocker from latest snapshot" is real
    evidence (`AISessionSnapshot.blockers`, filled in by the user when
    saving a snapshot) that no existing rule surfaced -- added here rather
    than in a separate engine, following the exact same pure-function-over-
    one-enriched-item shape as every other rule."""
    ai_sessions = item.get("ai_sessions") or {}
    snapshot = ai_sessions.get("latest_snapshot") or {}
    blocker = (snapshot.get("blockers") or "").strip()
    if not blocker:
        return None
    return _base(
        item,
        "Resolve the blocker from the latest snapshot",
        "The latest AI session snapshot recorded a blocker",
        [f"blockers: {blocker[:200]}"],
        priority=70,
        confidence=0.9,
    )


ALL_RULES: tuple[Callable[[dict[str, Any]], dict[str, Any] | None], ...] = (
    rule_inactive,
    rule_dirty_git_tree,
    rule_no_readme,
    rule_no_roadmap,
    rule_no_tests,
    rule_next_action_available,
    rule_high_value_low_activity,
    rule_high_move_risk,
    rule_momentum,
    rule_assets_no_commercial_output,
    rule_near_completion,
    rule_snapshot_blocker,
)


def generate_recommendations(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """`items` = `service.list_enriched_top_level_projects()`'s output.
    Excluded/internal-folder items never reach this function (that list is
    already top-level-projects-only), so exclusions can never leak into
    Advisor output."""
    recommendations: list[dict[str, Any]] = []
    for item in items:
        for rule in ALL_RULES:
            result = rule(item)
            if result is not None:
                recommendations.append(result)
    recommendations.sort(key=lambda r: r["priority"], reverse=True)
    return recommendations
