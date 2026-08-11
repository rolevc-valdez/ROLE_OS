"""The canonical `ImpactReport` shape and the risk-level vocabulary.

An `ImpactReport` answers one question -- "if this project changes, what
else is affected?" -- entirely from evidence the Project Ecosystem Engine
(Sprint C8), ProjectContext, and Operational Intelligence (Sprint C6)
already computed. Nothing here detects a new relationship; it only reads,
traverses (bounded), scores, and explains what Sprint C8's relationship
graph already found.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

# Ordered least-to-most severe -- `scoring.py` is the only place that
# picks one of these; every other module treats it as an opaque label.
RISK_LEVELS: tuple[str, ...] = ("none", "low", "medium", "high", "critical")

# Impact Categories (brief §"Impact Categories"): every recommended action/
# evidence line is implicitly attributable to one of these by which
# ImpactReport field it lives under -- this tuple exists so callers (UI,
# tests) have one place to enumerate them, not a second classification
# system.
IMPACT_CATEGORIES: tuple[str, ...] = (
    "assets",
    "documentation",
    "knowledge",
    "prompts",
    "sessions",
    "dependencies",
    "operational",
    "commercial",
    "release",
)


def project_ref(
    *,
    canonical_project_id: str | None,
    item_id: str | None = None,
    display_name: str | None = None,
) -> dict[str, Any]:
    return {
        "canonical_project_id": canonical_project_id,
        "item_id": item_id,
        "display_name": display_name or canonical_project_id or item_id or "Unknown project",
    }


def make_impact_report(
    *,
    project: dict[str, Any],
    overall_risk: str,
    confidence: float,
    affected_projects: list[dict[str, Any]],
    direct_dependencies: list[dict[str, Any]],
    transitive_dependencies: list[dict[str, Any]],
    shared_assets: list[dict[str, Any]],
    shared_prompts: list[dict[str, Any]],
    shared_documentation: list[dict[str, Any]],
    shared_knowledge: list[dict[str, Any]],
    shared_sessions: list[dict[str, Any]],
    operational_effects: list[str],
    release_effects: list[str],
    recommended_actions: list[str],
    evidence: list[str],
    limitations: list[str],
) -> dict[str, Any]:
    """The single place an `ImpactReport` dict gets constructed.

    Field semantics (the brief's own field names, disambiguated): `direct_
    dependencies`/`transitive_dependencies` are the projects *affected by*
    a change to `project` via the dependency chain -- i.e. projects that
    (directly, or via a further hop) depend on `project` -- not projects
    `project` itself depends on (that's a different question, already
    answered by `GET /project-ecosystem/{id}`'s own `dependencies` field).
    The worked example in the brief makes this concrete: for `project` =
    ROLE OS, `direct_dependencies` = [ROLE Commerce Factory] (depends on
    ROLE OS directly) and `transitive_dependencies` = [RoleValdez.com]
    (depends on ROLE Commerce Factory, which depends on ROLE OS)."""
    assert overall_risk in RISK_LEVELS, f"unsupported risk level: {overall_risk}"
    return {
        "project": project,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overall_risk": overall_risk,
        "confidence": round(max(0.0, min(1.0, float(confidence))), 2),
        "affected_projects": affected_projects,
        "direct_dependencies": direct_dependencies,
        "transitive_dependencies": transitive_dependencies,
        "shared_assets": shared_assets,
        "shared_prompts": shared_prompts,
        "shared_documentation": shared_documentation,
        "shared_knowledge": shared_knowledge,
        "shared_sessions": shared_sessions,
        "operational_effects": operational_effects,
        "release_effects": release_effects,
        "recommended_actions": recommended_actions,
        "evidence": evidence,
        "limitations": limitations,
    }
