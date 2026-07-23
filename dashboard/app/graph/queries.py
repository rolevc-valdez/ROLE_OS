"""Query Engine: traversal, pathfinding, impact analysis, and search over an
already-built `Graph`. Pure functions -- no I/O beyond the optional Advisor
lookup used by `impact_analysis` -- so any future AI provider (or a test)
can call these directly without touching the dashboard/API/UI layers.
"""

from __future__ import annotations

from collections import deque
from typing import Any

from app.advisor import db as advisor_db
from app.config import Settings, get_settings
from app.graph.models import Graph, Node


def find_node(graph: Graph, node_id_: str) -> Node | None:
    return graph.get_node(node_id_)


def find_nodes_by_label(graph: Graph, label: str, node_type: str | None = None) -> list[Node]:
    """Case-insensitive exact-or-substring match on node label, optionally
    restricted to one node type. Exact matches are ranked first."""
    needle = label.strip().lower()
    exact: list[Node] = []
    partial: list[Node] = []
    for node in graph.nodes:
        if node_type and node.type != node_type:
            continue
        hay = node.label.strip().lower()
        if hay == needle:
            exact.append(node)
        elif needle in hay:
            partial.append(node)
    return exact + partial


def search_nodes(
    graph: Graph, q: str, node_type: str | None = None, workspace: str | None = None, limit: int = 50
) -> list[dict[str, Any]]:
    needle = (q or "").strip().lower()
    results: list[Node] = []
    for node in graph.nodes:
        if node_type and node.type != node_type:
            continue
        if workspace:
            node_ws = node.data.get("workspace") if node.type == "Project" else None
            if node.type == "Workspace":
                node_ws = node.label
            if node_ws != workspace:
                continue
        if not needle or needle in node.label.strip().lower():
            results.append(node)
        if len(results) >= limit:
            break
    return [n.to_dict() for n in results]


def neighbors(
    graph: Graph,
    node_id_: str,
    *,
    direction: str = "both",
    edge_type: str | None = None,
    node_type: str | None = None,
    depth: int = 1,
) -> list[dict[str, Any]]:
    """BFS outward from `node_id_` up to `depth` hops.

    `direction` is one of "out", "in", "both". Returns a flat list of
    {"node": ..., "edge": ..., "distance": ...} entries, closest first,
    each node appearing only once (at its shortest distance).
    """
    if not graph.has_node(node_id_):
        return []

    def candidate_edges(nid: str) -> list:
        if direction == "out":
            return graph.edges_from(nid)
        if direction == "in":
            return graph.edges_to(nid)
        return graph.edges_touching(nid)

    visited = {node_id_}
    results: list[dict[str, Any]] = []
    frontier = deque([(node_id_, 0)])
    while frontier:
        current, dist = frontier.popleft()
        if dist >= depth:
            continue
        for edge in candidate_edges(current):
            if edge_type and edge.type != edge_type:
                continue
            other_id = edge.target if edge.source == current else edge.source
            if other_id in visited:
                continue
            other = graph.get_node(other_id)
            if other is None:
                continue
            if node_type and other.type != node_type:
                continue
            visited.add(other_id)
            results.append({"node": other.to_dict(), "edge": edge.to_dict(), "distance": dist + 1})
            frontier.append((other_id, dist + 1))
    return results


def shortest_path(graph: Graph, source_id: str, target_id: str, max_depth: int = 8) -> dict[str, Any] | None:
    """Unweighted BFS shortest path (both directions) between two nodes.

    Returns {"nodes": [...], "edges": [...]} or None if unreachable within
    `max_depth` hops.
    """
    if not graph.has_node(source_id) or not graph.has_node(target_id):
        return None
    if source_id == target_id:
        node = graph.get_node(source_id)
        return {"nodes": [node.to_dict()], "edges": []}

    visited = {source_id}
    parent: dict[str, tuple[str, Any]] = {}
    frontier = deque([(source_id, 0)])

    while frontier:
        current, dist = frontier.popleft()
        if dist >= max_depth:
            continue
        for edge in graph.edges_touching(current):
            other_id = edge.target if edge.source == current else edge.source
            if other_id in visited:
                continue
            visited.add(other_id)
            parent[other_id] = (current, edge)
            if other_id == target_id:
                path_nodes = [target_id]
                path_edges = [edge]
                node_cursor = current
                while node_cursor != source_id:
                    prev, prev_edge = parent[node_cursor]
                    path_nodes.append(node_cursor)
                    path_edges.append(prev_edge)
                    node_cursor = prev
                path_nodes.append(source_id)
                path_nodes.reverse()
                path_edges.reverse()
                return {
                    "nodes": [graph.get_node(n).to_dict() for n in path_nodes],
                    "edges": [e.to_dict() for e in path_edges],
                }
            frontier.append((other_id, dist + 1))
    return None


def impact_analysis(
    graph: Graph, node_id_: str, *, max_depth: int = 4, settings: Settings | None = None
) -> dict[str, Any] | None:
    """Cascading "what's affected if this node changes" traversal.

    Example (matching the Epic 3 spec): if a Project changes, which
    Projects are affected -> which Assets -> which Conversations -> which
    Capabilities -> which Advisor recommendations? This walks the whole
    reachable neighborhood (both directions, up to `max_depth` hops) and
    groups the result by node type, then separately looks up any live
    Advisor recommendations for every affected Project.
    """
    if not graph.has_node(node_id_):
        return None

    settings = settings or get_settings()
    reached = neighbors(graph, node_id_, direction="both", depth=max_depth)

    by_type: dict[str, list[dict[str, Any]]] = {t: [] for t in (
        "Project", "KnowledgeCard", "Conversation", "Capability", "Person",
        "Application", "Vendor", "Workspace", "Decision", "Deliverable",
        "Prompt", "Asset",
    )}
    for entry in reached:
        node = entry["node"]
        by_type.setdefault(node["type"], []).append(node)

    affected_project_ids = [
        n["data"].get("project_id") for n in by_type.get("Project", []) if n["data"].get("project_id")
    ]
    source_node = graph.get_node(node_id_)
    if source_node and source_node.type == "Project":
        affected_project_ids.append(source_node.data.get("project_id"))
    affected_project_ids = list(dict.fromkeys(pid for pid in affected_project_ids if pid))

    recommendations: list[dict[str, Any]] = []
    for pid in affected_project_ids:
        recommendations.extend(
            advisor_db.list_recommendations(project_id=pid, only_live=True, settings=settings)
        )

    return {
        "origin": source_node.to_dict() if source_node else None,
        "affected_by_type": by_type,
        "advisor_recommendations": recommendations,
        "total_affected": len(reached),
    }


# ---------------------------------------------------------------------------
# Named convenience queries matching the Epic 3 example questions.
# Thin wrappers over neighbors()/search so each example is directly testable
# and directly answerable through the generic /graph API.
# ---------------------------------------------------------------------------


def projects_related_to(graph: Graph, project_name: str) -> list[dict[str, Any]]:
    matches = find_nodes_by_label(graph, project_name, node_type="Project")
    if not matches:
        return []
    return neighbors(graph, matches[0].id, direction="both", node_type="Project", depth=1)


def capabilities_used_by(graph: Graph, project_name: str) -> list[dict[str, Any]]:
    matches = find_nodes_by_label(graph, project_name, node_type="Project")
    if not matches:
        return []
    return neighbors(graph, matches[0].id, direction="out", edge_type="USES", node_type="Capability", depth=1)


def applications_connected_to(graph: Graph, name: str) -> list[dict[str, Any]]:
    matches = find_nodes_by_label(graph, name)
    if not matches:
        return []
    return neighbors(graph, matches[0].id, direction="both", node_type="Application", depth=2)


def conversations_mentioning(graph: Graph, name: str) -> list[dict[str, Any]]:
    matches = find_nodes_by_label(graph, name)
    if not matches:
        return []
    target = matches[0]
    return neighbors(graph, target.id, direction="in", edge_type="MENTIONS", node_type="KnowledgeCard", depth=1)


def people_involved_in(graph: Graph, project_name: str) -> list[dict[str, Any]]:
    matches = find_nodes_by_label(graph, project_name, node_type="Project")
    if not matches:
        return []
    project_node = matches[0]
    direct = neighbors(graph, project_node.id, direction="out", edge_type="CREATED_BY", node_type="Person", depth=1)
    cards = neighbors(graph, project_node.id, direction="in", edge_type="BELONGS_TO", node_type="KnowledgeCard", depth=1)
    seen_ids = {entry["node"]["id"] for entry in direct}
    for card_entry in cards:
        for person_entry in neighbors(graph, card_entry["node"]["id"], direction="out", edge_type="MENTIONS", node_type="Person", depth=1):
            if person_entry["node"]["id"] not in seen_ids:
                seen_ids.add(person_entry["node"]["id"])
                direct.append(person_entry)
    return direct


def projects_blocked_by(graph: Graph, project_name: str) -> list[dict[str, Any]]:
    """Projects that depend on `project_name` (i.e. are blocked if it stalls)."""
    matches = find_nodes_by_label(graph, project_name, node_type="Project")
    if not matches:
        return []
    return neighbors(graph, matches[0].id, direction="in", edge_type="DEPENDS_ON", node_type="Project", depth=1)


def projects_unlocked_by_finishing(graph: Graph, project_name: str) -> list[dict[str, Any]]:
    """Projects unlocked by finishing `project_name` (its UNBLOCKS targets)."""
    matches = find_nodes_by_label(graph, project_name, node_type="Project")
    if not matches:
        return []
    return neighbors(graph, matches[0].id, direction="out", edge_type="UNBLOCKS", node_type="Project", depth=1)
