"""The Project Ecosystem Engine's public entry points.

`compute_relationships` runs every registered detector exactly once over
an already-computed `all_contexts` list (never re-fetched here -- pass in
`app.project_context.builder.all_project_contexts()`'s result if the
caller already has it, e.g. Mission Control/Project Memory, so the whole-
workspace context build never happens twice in one request), dedupes, and
applies manual overrides. `get_project_ecosystem` is the one per-project
view every consumer (the API, Explorer, Project Memory, Mission Control)
reads instead of independently walking the relationship list.
"""

from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.project_ecosystem import graph as graph_module
from app.project_ecosystem import relationships as relationships_module
from app.project_ecosystem.detectors import ALL_DETECTORS


def _project_key(ref: dict[str, Any]) -> str:
    return ref.get("canonical_project_id") or ref.get("item_id") or ref.get("display_name") or ""


def compute_relationships(
    all_contexts: list[dict[str, Any]] | None = None,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    """Runs the full detector registry once. `all_contexts` defaults to a
    fresh `all_project_contexts()` call only when the caller doesn't
    already have one -- every existing consumer in this codebase (Mission
    Control, Project Memory, Explorer) already computed it for the same
    request and should pass it straight through."""
    settings = settings or get_settings()
    if all_contexts is None:
        from app.project_context.builder import all_project_contexts

        all_contexts, _enriched_items = all_project_contexts(settings=settings)

    raw: list[dict[str, Any]] = []
    for detector in ALL_DETECTORS:
        raw.extend(detector(all_contexts, settings))

    deduped = relationships_module.dedupe(raw)
    return relationships_module.apply_overrides(deduped, settings=settings)


def get_project_ecosystem(
    project_id: str,
    settings: Settings | None = None,
    *,
    all_contexts: list[dict[str, Any]] | None = None,
    relationships: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """The one per-project ecosystem view. `project_id` is a canonical PI
    project id (matches `ProjectContext.id`/`.canonical_project_id`).
    Returns `None` only if the project doesn't resolve to any tracked
    project at all -- an adopted project with zero detected relationships
    still returns a real (all-empty) ecosystem, not `None`."""
    settings = settings or get_settings()

    if all_contexts is None:
        from app.project_context.builder import all_project_contexts

        all_contexts, _enriched_items = all_project_contexts(settings=settings)

    context = next(
        (c for c in all_contexts if c.get("id") == project_id or c.get("item_id") == project_id),
        None,
    )
    if context is None:
        return None

    if relationships is None:
        relationships = compute_relationships(all_contexts=all_contexts, settings=settings)

    project_key = _project_key(
        {"canonical_project_id": context.get("id"), "item_id": context.get("item_id")}
    )
    graph = graph_module.build_graph(relationships)

    node = graph.get(project_key, {"out": [], "in": []})
    project_relationships = node["out"] + node["in"]

    return {
        "project": {
            "canonical_project_id": context.get("id"),
            "item_id": context.get("item_id"),
            "display_name": context.get("display_name"),
        },
        "relationships": project_relationships,
        "dependencies": graph_module.dependencies_of(graph, project_key),
        "consumers": graph_module.dependents_of(graph, project_key),
        "blocks": graph_module.blocks_of(graph, project_key),
        "blocked_by": graph_module.blocked_by_of(graph, project_key),
        "shared_assets": graph_module.shares_of(graph, project_key, "shares_assets"),
        "shared_prompts": graph_module.shares_of(graph, project_key, "shares_prompts"),
        "shared_documents": graph_module.shares_of(graph, project_key, "shares_documentation"),
        "shared_knowledge": graph_module.shares_of(graph, project_key, "shares_knowledge"),
        "shared_sessions": graph_module.shares_of(graph, project_key, "shares_sessions"),
        "impact_summary": graph_module.impact_summary(graph, project_key),
    }
