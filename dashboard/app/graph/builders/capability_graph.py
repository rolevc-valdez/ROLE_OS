"""Builds Capability nodes and the edges around them.

- Project -[IMPLEMENTS]-> Capability          (provider exposes it)
- Project -[USES]-> Capability                (consumer uses it)
- Project -[SHARES_CAPABILITY]-> Project      (consumer <-> provider,
  precomputed convenience edge so a project-to-project view of capability
  sharing doesn't require hopping through the Capability node.)
"""

from __future__ import annotations

from typing import Any

from app.graph.models import Edge, Node, node_id


def build(
    capabilities: list[dict[str, Any]],
    consumers_by_capability: dict[str, list[dict[str, Any]]],
) -> tuple[list[Node], list[Edge]]:
    """`capabilities` are rows from the capabilities table.
    `consumers_by_capability` maps capability_id -> list of consumer rows
    (each with at least `consumer_project_id`), as returned by
    `app.projects.db.list_capability_consumers`.
    """
    nodes: list[Node] = []
    edges: list[Edge] = []

    for cap in capabilities:
        cid = node_id("Capability", cap["id"])
        provider_pid = node_id("Project", cap["project_id"])
        nodes.append(
            Node(
                id=cid,
                type="Capability",
                label=cap["name"],
                data={"description": cap.get("description", ""), "category": cap.get("category", "")},
            )
        )
        edges.append(Edge(source=provider_pid, target=cid, type="IMPLEMENTS"))

        for consumer in consumers_by_capability.get(cap["id"], []):
            consumer_pid = node_id("Project", consumer["consumer_project_id"])
            edges.append(Edge(source=consumer_pid, target=cid, type="USES"))
            edges.append(Edge(source=consumer_pid, target=provider_pid, type="SHARES_CAPABILITY", data={"capability_id": cap["id"]}))

    return nodes, edges
