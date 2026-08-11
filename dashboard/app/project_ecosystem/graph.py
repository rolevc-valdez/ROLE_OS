"""A thin in-memory adjacency view over an already-computed relationship
list, plus the Impact Summary calculation. No graph database, no
persisted graph -- this is a plain dict built fresh from
`service.compute_relationships`'s output for the lifetime of one request,
matching the brief's "no graph dump" / "clean cards, not a visualization"
constraint: nothing here is meant to be rendered as a graph, only queried
for "who's connected to this project, and how."
"""

from __future__ import annotations

from typing import Any

# High risk: this project blocks 3+ others, or is itself blocked.
# Medium: 1-2 dependents/blocks. Low: any other relationship exists.
# None: no relationships at all. Fixed, documented thresholds -- not a
# hidden score.
_HIGH_RISK_DEPENDENT_THRESHOLD = 3


def _project_key(ref: dict[str, Any]) -> str:
    return ref.get("canonical_project_id") or ref.get("item_id") or ref.get("display_name") or ""


def build_graph(relationships: list[dict[str, Any]]) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """`{project_key: {"out": [relationship, ...], "in": [relationship, ...]}}`
    -- `out` = relationships where this project is `source_project`, `in`
    = where it's `target_project`."""
    graph: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for rel in relationships:
        source_key = _project_key(rel["source_project"])
        target_key = _project_key(rel["target_project"])
        graph.setdefault(source_key, {"out": [], "in": []})["out"].append(rel)
        graph.setdefault(target_key, {"out": [], "in": []})["in"].append(rel)
    return graph


def _by_type(rels: list[dict[str, Any]], relationship_type: str) -> list[dict[str, Any]]:
    return [r for r in rels if r["relationship_type"] == relationship_type]


def dependencies_of(graph: dict[str, Any], project_key: str) -> list[dict[str, Any]]:
    """Projects this one depends on."""
    return _by_type(graph.get(project_key, {}).get("out", []), "depends_on")


def dependents_of(graph: dict[str, Any], project_key: str) -> list[dict[str, Any]]:
    """Projects that depend on this one (a.k.a. "consumers" of it)."""
    return _by_type(graph.get(project_key, {}).get("in", []), "depends_on")


def blocks_of(graph: dict[str, Any], project_key: str) -> list[dict[str, Any]]:
    return _by_type(graph.get(project_key, {}).get("out", []), "blocks")


def blocked_by_of(graph: dict[str, Any], project_key: str) -> list[dict[str, Any]]:
    return _by_type(graph.get(project_key, {}).get("out", []), "blocked_by")


def shares_of(
    graph: dict[str, Any], project_key: str, relationship_type: str
) -> list[dict[str, Any]]:
    """Sharing relationships are symmetric by construction (each detector
    emits one direction only, but the underlying fact is mutual) -- look
    in both `out` and `in`."""
    node = graph.get(project_key, {"out": [], "in": []})
    return _by_type(node["out"], relationship_type) + _by_type(node["in"], relationship_type)


def impact_summary(graph: dict[str, Any], project_key: str) -> dict[str, Any]:
    """§ "Impact Summary": what changes if this project changes. Bounded
    to this project's direct (1-hop) relationships only -- no multi-hop
    traversal, no graph dump, matching the brief's "small bounded section"
    intent for anything ecosystem-related shown to a user."""
    node = graph.get(project_key, {"out": [], "in": []})
    all_rels = node["out"] + node["in"]

    dependents = dependents_of(graph, project_key)
    blocks = blocks_of(graph, project_key)
    blocked_by = blocked_by_of(graph, project_key)

    affected_keys: set[str] = set()
    for rel in all_rels:
        affected_keys.add(_project_key(rel["source_project"]))
        affected_keys.add(_project_key(rel["target_project"]))
    affected_keys.discard(project_key)

    affected_projects = []
    seen_refs: set[str] = set()
    for rel in all_rels:
        for ref in (rel["source_project"], rel["target_project"]):
            key = _project_key(ref)
            if key != project_key and key not in seen_refs:
                seen_refs.add(key)
                affected_projects.append(ref)

    shared_assets = shares_of(graph, project_key, "shares_assets")
    shared_documents = shares_of(graph, project_key, "shares_documentation")
    shared_prompts = shares_of(graph, project_key, "shares_prompts")
    shared_knowledge = shares_of(graph, project_key, "shares_knowledge")
    shared_sessions = shares_of(graph, project_key, "shares_sessions")

    if blocks or len(dependents) >= _HIGH_RISK_DEPENDENT_THRESHOLD:
        risk = "high"
    elif blocked_by or dependents:
        risk = "medium"
    elif all_rels:
        risk = "low"
    else:
        risk = "none"

    confidence = (
        round(sum(r["confidence"] for r in all_rels) / len(all_rels), 2) if all_rels else 0.0
    )

    return {
        "affected_projects": affected_projects,
        "shared_assets": shared_assets,
        "shared_documents": shared_documents,
        "shared_prompts": shared_prompts,
        "shared_knowledge": shared_knowledge,
        "shared_sessions": shared_sessions,
        "risk": risk,
        "confidence": confidence,
    }
