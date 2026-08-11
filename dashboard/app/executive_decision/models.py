"""Canonical `ExecutiveDecision` shape (Sprint C10).

ROLE OS's foundational domains (Project Context, Mission Control,
Operational Intelligence, Project Memory, Impact Analysis, Project
Ecosystem, Assets, Knowledge, Discovery, AI Sessions/Snapshots,
Workspace) already answer "what is true about each project." This is the
one place that turns those facts into a single decision: which project
to work on next, and why. No detector, no filesystem scan, no new
"project" concept -- every field here is either read verbatim from an
existing canonical service or computed by `scoring.py`/`planner.py` over
data those services already returned.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

RISK_LEVELS: tuple[str, ...] = ("none", "low", "medium", "high", "critical")


def project_ref(
    *,
    item_id: str | None = None,
    canonical_project_id: str | None = None,
    display_name: str | None = None,
) -> dict[str, Any] | None:
    if not item_id and not canonical_project_id:
        return None
    return {
        "item_id": item_id,
        "canonical_project_id": canonical_project_id,
        "display_name": display_name or item_id or canonical_project_id,
    }


def make_ranked_project(
    *,
    rank: int,
    project: dict[str, Any],
    decision_score: float,
    confidence: float,
    top_reasons: list[str],
) -> dict[str, Any]:
    return {
        "rank": rank,
        "project": project,
        "decision_score": round(decision_score, 1),
        "confidence": round(confidence, 2),
        "top_reasons": list(top_reasons),
    }


def make_today_plan_step(
    *,
    start_time: str,
    action: str,
    project: dict[str, Any] | None,
    objective: str,
    expected_duration: str,
    expected_result: str,
    dependencies_status: str,
    next_checkpoint: str,
) -> dict[str, Any]:
    return {
        "start_time": start_time,
        "action": action,
        "project": project,
        "objective": objective,
        "expected_duration": expected_duration,
        "expected_result": expected_result,
        "dependencies_status": dependencies_status,
        "next_checkpoint": next_checkpoint,
    }


def make_executive_decision(
    *,
    recommended_project: dict[str, Any] | None,
    decision_score: float,
    confidence: float,
    reason: str,
    expected_benefit: str,
    estimated_effort: str,
    estimated_duration: str,
    blocking_projects: list[str],
    projects_unblocked: list[str],
    commercial_value: str,
    technical_value: str,
    risk: str,
    dependencies: dict[str, Any],
    today_plan: list[dict[str, Any]],
    expected_result: str,
    evidence: list[str],
    limitations: list[str],
) -> dict[str, Any]:
    assert risk in RISK_LEVELS, f"unsupported risk level: {risk}"
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "recommended_project": recommended_project,
        "decision_score": round(decision_score, 1),
        "confidence": round(max(0.0, min(1.0, confidence)), 2),
        "reason": reason,
        "expected_benefit": expected_benefit,
        "estimated_effort": estimated_effort,
        "estimated_duration": estimated_duration,
        "blocking_projects": list(blocking_projects),
        "projects_unblocked": list(projects_unblocked),
        "commercial_value": commercial_value,
        "technical_value": technical_value,
        "risk": risk,
        "dependencies": dependencies,
        "today_plan": today_plan,
        "expected_result": expected_result,
        "evidence": list(evidence),
        "limitations": list(limitations),
    }
