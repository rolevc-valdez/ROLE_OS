"""The Executive Decision Engine's one public entry point (Sprint C10).

Answers "what should I work on next?" by composing already-computed
evidence from every existing canonical domain -- Project Context,
Operational Intelligence (Sprint C6), Project Ecosystem (Sprint C8),
Impact Analysis (Sprint C9), and Project Memory's own pending-work/next-
action synthesis (Sprint C7.1, reused via direct import, never
re-implemented). No new detector, no new relationship type, no new
filesystem/knowledge scan, no LLM/embeddings/vector database. Every
adopted project is scored once (`scoring.compute_decision_score`),
ranked, and the single top project -- deterministically tie-broken, never
a tie -- becomes the recommended decision.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.config import Settings, get_settings
from app.executive_decision.models import make_executive_decision, project_ref
from app.executive_decision.planner import (
    build_today_plan,
    dependencies_status,
    estimate_effort_and_duration,
)
from app.executive_decision.scoring import compute_decision_score
from app.project_ecosystem import graph as graph_module

_MAX_LIMITATIONS = [
    (
        "Scores are additive and fixed (see `scoring.py`'s point table), never a "
        "learned/hidden weighting -- every non-zero contribution is named in "
        "`evidence`."
    ),
    (
        "Only adopted projects compete -- a merely-discovered, unadopted folder is "
        "never scored or recommended (Project Ecosystem/Impact Analysis's own "
        "security boundary, inherited here unchanged)."
    ),
    (
        "Today's Plan is a single deterministic step (the one recommended "
        "project), not a scheduling engine -- '09:00' is a fixed label, not a "
        "real-clock computation, and there is no calendar integration."
    ),
    (
        "Estimated effort/duration are a static keyword lookup over the "
        "recommended action's own title (the same convention `operational_"
        "intelligence.models.expected_benefit_for` already established), never a "
        "generated per-project estimate."
    ),
]


def _project_key(ref: dict[str, Any]) -> str:
    return ref.get("canonical_project_id") or ref.get("item_id") or ref.get("display_name") or ""


def _top_recommendation_for(
    canonical_project_id: str, operational_intelligence_recs: list[dict[str, Any]]
) -> dict[str, Any] | None:
    return next(
        (
            r
            for r in operational_intelligence_recs
            if (r.get("project") or {}).get("canonical_project_id") == canonical_project_id
        ),
        None,
    )


def _days_since(timestamp: str | None) -> float | None:
    if not timestamp:
        return None
    try:
        ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return (datetime.now(timezone.utc) - ts).total_seconds() / 86400.0


def _pending_work_for(context: dict[str, Any], recommendation: dict[str, Any] | None) -> str:
    """Reuses Project Memory's own pending-work synthesis (Sprint C7.1/
    hotfix) directly -- never re-implements the snapshot -> Next Action ->
    Operational Intelligence fallback chain a second time."""
    from app.project_memory.service import _pending_work as project_memory_pending_work

    next_action = context.get("next_action") or {}
    snapshot = context.get("latest_snapshot")
    return project_memory_pending_work(snapshot, next_action, recommendation)


def _next_action_text_for(context: dict[str, Any], recommendation: dict[str, Any] | None) -> str:
    """Reuses Project Memory's own Next Action display fallback (file-based
    text -> Operational Intelligence's `suggested_action`) -- same reason
    as `_pending_work_for`."""
    from app.project_memory.service import _next_action_output as project_memory_next_action

    next_action = context.get("next_action") or {}
    return project_memory_next_action(next_action, recommendation).get("text") or ""


def _score_project(
    context: dict[str, Any],
    *,
    operational_intelligence_recs: list[dict[str, Any]],
    graph: dict[str, Any],
    settings: Settings,
    all_contexts: list[dict[str, Any]],
    enriched_items: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    is_data_stale: bool,
) -> dict[str, Any]:
    from app.impact_analysis import get_impact_analysis

    canonical_id = context.get("id")
    project_key = _project_key(
        {"canonical_project_id": canonical_id, "item_id": context.get("item_id")}
    )

    top_recommendation = _top_recommendation_for(canonical_id, operational_intelligence_recs)
    dependents = graph_module.dependents_of(graph, project_key)
    blocks = graph_module.blocks_of(graph, project_key)
    dependencies = graph_module.dependencies_of(graph, project_key)
    dependent_names = sorted({r["source_project"]["display_name"] for r in dependents})
    blocked_names = sorted({r["target_project"]["display_name"] for r in blocks})
    dependency_names = sorted({r["target_project"]["display_name"] for r in dependencies})

    impact = get_impact_analysis(
        canonical_id,
        settings=settings,
        all_contexts=all_contexts,
        enriched_items=enriched_items,
        relationships=relationships,
        operational_intelligence_recs=operational_intelligence_recs,
    )
    overall_risk = impact["overall_risk"] if impact else "none"

    pending_work = _pending_work_for(context, top_recommendation)
    days_since_activity = _days_since(context.get("latest_activity"))

    score, confidence, evidence = compute_decision_score(
        top_recommendation=top_recommendation,
        business_value=context.get("business_value"),
        dependent_names=dependent_names,
        blocked_names=blocked_names,
        overall_risk=overall_risk,
        pending_work=pending_work,
        days_since_activity=days_since_activity,
        health_score=context.get("health_score"),
        status=context.get("status"),
        is_data_stale=is_data_stale,
    )

    return {
        "context": context,
        "top_recommendation": top_recommendation,
        "dependent_names": dependent_names,
        "blocked_names": blocked_names,
        "dependency_names": dependency_names,
        "overall_risk": overall_risk,
        "pending_work": pending_work,
        "score": score,
        "confidence": confidence,
        "evidence": evidence,
    }


def _sort_key(candidate: dict[str, Any]) -> tuple[float, int, str]:
    """Deterministic total order -- never a tie. Primary: decision score
    (desc). Tie-break 1: project health score (desc; a healthier project
    is the safer next bet when two score identically). Tie-break 2:
    canonical project id (asc; a fixed, arbitrary-but-stable last resort
    so the exact same input always produces the exact same winner)."""
    context = candidate["context"]
    return (
        -candidate["score"],
        -(context.get("health_score") or 0),
        context.get("id") or "",
    )


def _technical_value(context: dict[str, Any]) -> str:
    health = context.get("health")
    return {"healthy": "High", "warning": "Medium", "critical": "Low"}.get(health, "Unknown")


def _commercial_value(business_value: str | None) -> str:
    if not business_value:
        return "Unknown"
    return business_value.capitalize()


def get_executive_decision(
    settings: Settings | None = None,
    *,
    all_contexts: list[dict[str, Any]] | None = None,
    enriched_items: list[dict[str, Any]] | None = None,
    operational_intelligence_recs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """The one Executive Decision entry point. Pass `all_contexts`/
    `enriched_items`/`operational_intelligence_recs` when the caller (e.g.
    Mission Control) already computed them in this request -- this
    function never repeats a whole-workspace pass that already happened.
    Returns `{"decision": ExecutiveDecision, "ranked_projects": [...]}`."""
    settings = settings or get_settings()

    if all_contexts is None or enriched_items is None:
        from app.project_context.builder import all_project_contexts

        all_contexts, enriched_items = all_project_contexts(settings=settings)

    adopted_contexts = [c for c in all_contexts if c.get("is_adopted")]

    if operational_intelligence_recs is None:
        from app.operational_intelligence import get_operational_intelligence

        operational_intelligence_recs = get_operational_intelligence(
            settings=settings, all_contexts=all_contexts, enriched_items=enriched_items
        )

    from app.workspace.service import get_freshness

    is_data_stale = bool(get_freshness(settings=settings).get("is_stale"))

    from app.project_ecosystem import compute_relationships

    relationships = compute_relationships(all_contexts=all_contexts, settings=settings)
    graph = graph_module.build_graph(relationships)

    candidates = [
        _score_project(
            context,
            operational_intelligence_recs=operational_intelligence_recs,
            graph=graph,
            settings=settings,
            all_contexts=all_contexts,
            enriched_items=enriched_items,
            relationships=relationships,
            is_data_stale=is_data_stale,
        )
        for context in adopted_contexts
    ]
    candidates.sort(key=_sort_key)

    ranked_projects = [
        {
            "rank": i + 1,
            "project": project_ref(
                canonical_project_id=c["context"].get("id"),
                item_id=c["context"].get("item_id"),
                display_name=c["context"].get("display_name"),
            ),
            "decision_score": round(c["score"], 1),
            "confidence": round(c["confidence"], 2),
            "top_reasons": c["evidence"][:3],
        }
        for i, c in enumerate(candidates)
    ]

    if not candidates:
        decision = make_executive_decision(
            recommended_project=None,
            decision_score=0.0,
            confidence=0.0,
            reason="No adopted projects to recommend from -- adopt a project on the Workspace page first.",
            expected_benefit="",
            estimated_effort="",
            estimated_duration="",
            blocking_projects=[],
            projects_unblocked=[],
            commercial_value="Unknown",
            technical_value="Unknown",
            risk="none",
            dependencies={"depends_on": [], "status": "Satisfied"},
            today_plan=[],
            expected_result="",
            evidence=[],
            limitations=_MAX_LIMITATIONS,
        )
        return {"decision": decision, "ranked_projects": []}

    winner = candidates[0]
    context = winner["context"]
    project = project_ref(
        canonical_project_id=context.get("id"),
        item_id=context.get("item_id"),
        display_name=context.get("display_name"),
    )

    action_title = (
        winner["top_recommendation"]["recommendation"]
        if winner["top_recommendation"]
        else _next_action_text_for(context, winner["top_recommendation"]) or "Continue this project"
    )
    objective = _next_action_text_for(context, winner["top_recommendation"]) or action_title
    expected_benefit = (
        winner["top_recommendation"]["expected_benefit"]
        if winner["top_recommendation"]
        else "Keeps momentum on the highest-scoring project in the portfolio."
    )
    effort, duration = estimate_effort_and_duration(action_title)
    dep_status = dependencies_status(
        [
            name
            for name in winner["dependency_names"]
            if any(
                (c.get("display_name") == name)
                and ((c.get("status") or "").lower() in ("blocked", "at_risk"))
                for c in all_contexts
            )
        ]
    )
    expected_result = (
        f"{objective} moves to a checkpoint-able state"
        if objective
        else "Meaningful progress recorded"
    )

    reason_parts = winner["evidence"][:3]
    reason = (
        "; ".join(reason_parts)
        if reason_parts
        else "Highest-ranked adopted project with no other candidate scoring higher."
    )

    today_plan = build_today_plan(
        project=project,
        action_title=action_title,
        objective=objective,
        expected_duration=duration,
        expected_result=expected_result,
        dependency_status=dep_status,
    )

    decision = make_executive_decision(
        recommended_project=project,
        decision_score=winner["score"],
        confidence=winner["confidence"],
        reason=reason,
        expected_benefit=expected_benefit,
        estimated_effort=effort,
        estimated_duration=duration,
        blocking_projects=winner["blocked_names"],
        projects_unblocked=winner["dependent_names"],
        commercial_value=_commercial_value(context.get("business_value")),
        technical_value=_technical_value(context),
        risk=winner["overall_risk"],
        dependencies={"depends_on": winner["dependency_names"], "status": dep_status},
        today_plan=today_plan,
        expected_result=expected_result,
        evidence=winner["evidence"],
        limitations=_MAX_LIMITATIONS,
    )

    return {"decision": decision, "ranked_projects": ranked_projects}
