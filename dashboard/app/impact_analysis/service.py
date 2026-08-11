"""The Impact Analysis Engine's one public entry point.

Answers "if this project changes, what else is affected?" entirely by
reading the Project Ecosystem Engine's already-computed relationship
graph (Sprint C8 -- `compute_relationships`/`graph.build_graph`, never a
second relationship-detection pass), ProjectContext (business value,
health, next action of affected projects), and Operational Intelligence
(Sprint C6 -- existing recommendations for affected projects). No new
graph, no new relationship type, no filesystem/knowledge scan of its own.
"""

from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.impact_analysis.models import make_impact_report, project_ref
from app.impact_analysis.scoring import average_confidence, compute_overall_risk
from app.project_ecosystem import graph as graph_module

# Bounded transitive traversal (brief: "Limit traversal depth", "Avoid
# cycles"). 3 hops covers the brief's own worked example (ROLE OS ->
# ROLE Commerce Factory -> RoleValdez.com is 2 hops) with headroom for one
# more, without risking an unbounded/hard-to-read report on a deeply
# chained workspace.
MAX_TRANSITIVE_DEPTH = 3

_LIMITATIONS = [
    (
        "Transitive traversal follows only explicit `depends_on` relationships "
        f"(Sprint C8), bounded to {MAX_TRANSITIVE_DEPTH} hops -- a real but "
        "undeclared dependency (no PI dependency edge created for it) is not "
        "traversed."
    ),
    (
        "Shared-assets/knowledge/documentation/prompts/sessions evidence reflects "
        "the Project Ecosystem Engine's own detectors and their documented "
        "confidence levels -- see that engine's known limitations (no import/"
        "package-reference parsing; name-mention detectors are literal "
        "substring matches)."
    ),
    (
        "Operational/release effects are read from each affected project's "
        "existing Operational Intelligence recommendation and business_value/"
        "health, never independently assessed."
    ),
]


def _key(ref: dict[str, Any]) -> str:
    return ref.get("canonical_project_id") or ref.get("item_id") or ref.get("display_name") or ""


def _traverse_dependents(
    graph: dict[str, Any], start_key: str, *, max_depth: int
) -> list[dict[str, Any]]:
    """Bounded BFS over `depends_on` edges, reversed (who depends on this
    project, then who depends on those, ...). A visited set keyed by
    project identity guarantees no cycle is ever re-entered and no
    project is ever listed twice, regardless of how many paths reach it."""
    visited = {start_key}
    frontier = [start_key]
    hops: list[dict[str, Any]] = []
    for depth in range(1, max_depth + 1):
        next_frontier: list[str] = []
        for key in frontier:
            for rel in graph_module.dependents_of(graph, key):
                dependent_key = _key(rel["source_project"])
                if dependent_key in visited:
                    continue
                visited.add(dependent_key)
                hops.append({"depth": depth, "relationship": rel})
                next_frontier.append(dependent_key)
        frontier = next_frontier
        if not frontier:
            break
    return hops


def _operational_effects(
    affected_canonical_ids: set[str],
    all_contexts: list[dict[str, Any]],
    enriched_items: list[dict[str, Any]],
    settings: Settings,
    *,
    operational_intelligence_recs: list[dict[str, Any]] | None,
) -> list[str]:
    """`operational_intelligence_recs`, when the caller already computed
    it in this request (e.g. Project Memory, which also needs the top
    Operational Recommendation for this same project), is reused verbatim
    -- calling `get_operational_intelligence` a second time in the same
    request would repeat a whole-workspace Epic 2 Advisor refresh for no
    benefit."""
    if not affected_canonical_ids:
        return []
    if operational_intelligence_recs is None:
        from app.operational_intelligence import get_operational_intelligence

        operational_intelligence_recs = get_operational_intelligence(
            settings=settings, all_contexts=all_contexts, enriched_items=enriched_items
        )
    effects = []
    for rec in operational_intelligence_recs:
        project = rec.get("project")
        if not project or project.get("canonical_project_id") not in affected_canonical_ids:
            continue
        effects.append(f"{project['display_name']}: {rec['recommendation']} ({rec['reason']})")
    return effects


def _release_effects(
    affected_canonical_ids: set[str], all_contexts: list[dict[str, Any]]
) -> list[str]:
    effects = []
    for context in all_contexts:
        if context.get("id") not in affected_canonical_ids:
            continue
        business_value = (context.get("business_value") or "").lower()
        if business_value in ("high", "critical"):
            effects.append(
                f"{context['display_name']} has business_value='{business_value}' -- "
                "verify its release readiness before/after this change"
            )
        if (context.get("git") or {}).get("is_dirty"):
            effects.append(
                f"{context['display_name']} has uncommitted changes -- coordinate before releasing"
            )
    return effects


def _recommended_actions(
    *,
    direct_count: int,
    transitive_count: int,
    shared_counts: dict[str, int],
    release_effects: list[str],
) -> list[str]:
    actions = []
    if direct_count:
        actions.append(
            f"Notify {direct_count} directly dependent project(s) before making breaking changes"
        )
    if transitive_count:
        actions.append(
            f"Review {transitive_count} transitively affected project(s) for downstream impact"
        )
    if shared_counts.get("shares_assets"):
        actions.append("Verify shared assets remain compatible after this change")
    if shared_counts.get("shares_documentation"):
        actions.append("Update cross-referenced documentation in affected projects")
    if shared_counts.get("shares_knowledge"):
        actions.append("Review shared knowledge/decisions for continued accuracy")
    if release_effects:
        actions.append("Re-verify release readiness for affected commercial/dirty projects")
    if not actions:
        actions.append(
            "No coordinated action needed -- no dependent or shared-evidence projects detected"
        )
    return actions


def get_impact_analysis(
    project_id: str,
    settings: Settings | None = None,
    *,
    all_contexts: list[dict[str, Any]] | None = None,
    enriched_items: list[dict[str, Any]] | None = None,
    relationships: list[dict[str, Any]] | None = None,
    operational_intelligence_recs: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """The one Impact Analysis entry point. Pass `all_contexts`/
    `enriched_items`/`relationships`/`operational_intelligence_recs` when
    the caller already computed them
    in this request (Mission Control, Project Memory, Explorer) -- this
    function never repeats a filesystem scan or relationship-detection
    pass that already happened."""
    settings = settings or get_settings()

    if all_contexts is None or enriched_items is None:
        from app.project_context.builder import all_project_contexts

        all_contexts, enriched_items = all_project_contexts(settings=settings)

    context = next(
        (c for c in all_contexts if c.get("id") == project_id or c.get("item_id") == project_id),
        None,
    )
    if context is None:
        return None

    if relationships is None:
        from app.project_ecosystem import compute_relationships

        relationships = compute_relationships(all_contexts=all_contexts, settings=settings)

    graph = graph_module.build_graph(relationships)
    project_key = _key(
        {"canonical_project_id": context.get("id"), "item_id": context.get("item_id")}
    )

    hops = _traverse_dependents(graph, project_key, max_depth=MAX_TRANSITIVE_DEPTH)
    direct_hops = [h for h in hops if h["depth"] == 1]
    transitive_hops = [h for h in hops if h["depth"] > 1]
    direct_dependencies = [h["relationship"] for h in direct_hops]
    transitive_dependencies = [h["relationship"] for h in transitive_hops]

    shared_assets = graph_module.shares_of(graph, project_key, "shares_assets")
    shared_prompts = graph_module.shares_of(graph, project_key, "shares_prompts")
    shared_documentation = graph_module.shares_of(graph, project_key, "shares_documentation")
    shared_knowledge = graph_module.shares_of(graph, project_key, "shares_knowledge")
    shared_sessions = graph_module.shares_of(graph, project_key, "shares_sessions")
    blocks = graph_module.blocks_of(graph, project_key)

    shared_counts = {
        "shares_assets": len(shared_assets),
        "shares_prompts": len(shared_prompts),
        "shares_documentation": len(shared_documentation),
        "shares_knowledge": len(shared_knowledge),
        "shares_sessions": len(shared_sessions),
    }

    # affected_projects: the union of everyone named in any relationship
    # above -- one entry per project, in first-seen order.
    affected_refs: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    all_relevant_rels = (
        direct_dependencies
        + transitive_dependencies
        + shared_assets
        + shared_prompts
        + shared_documentation
        + shared_knowledge
        + shared_sessions
    )
    for rel in all_relevant_rels:
        for ref in (rel["source_project"], rel["target_project"]):
            key = _key(ref)
            if key != project_key and key not in seen_keys:
                seen_keys.add(key)
                affected_refs.append(ref)

    affected_canonical_ids = {
        ref["canonical_project_id"] for ref in affected_refs if ref.get("canonical_project_id")
    }

    overall_risk, risk_reasons = compute_overall_risk(
        direct_dependents=direct_dependencies,
        transitive_dependents=transitive_dependencies,
        blocks=blocks,
        shared_counts=shared_counts,
    )
    confidence = average_confidence(all_relevant_rels + blocks)

    operational_effects = _operational_effects(
        affected_canonical_ids,
        all_contexts,
        enriched_items,
        settings,
        operational_intelligence_recs=operational_intelligence_recs,
    )
    release_effects = _release_effects(affected_canonical_ids, all_contexts)
    recommended_actions = _recommended_actions(
        direct_count=len(direct_dependencies),
        transitive_count=len(transitive_dependencies),
        shared_counts=shared_counts,
        release_effects=release_effects,
    )

    evidence = list(risk_reasons)
    for rel in all_relevant_rels + blocks:
        evidence.extend(rel["evidence"])

    return make_impact_report(
        project=project_ref(
            canonical_project_id=context.get("id"),
            item_id=context.get("item_id"),
            display_name=context.get("display_name"),
        ),
        overall_risk=overall_risk,
        confidence=confidence,
        affected_projects=affected_refs,
        direct_dependencies=direct_dependencies,
        transitive_dependencies=transitive_dependencies,
        shared_assets=shared_assets,
        shared_prompts=shared_prompts,
        shared_documentation=shared_documentation,
        shared_knowledge=shared_knowledge,
        shared_sessions=shared_sessions,
        operational_effects=operational_effects,
        release_effects=release_effects,
        recommended_actions=recommended_actions,
        evidence=evidence,
        limitations=_LIMITATIONS,
    )
