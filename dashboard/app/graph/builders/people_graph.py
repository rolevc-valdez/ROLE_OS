"""Builds Person nodes, deduplicated by name across every source:

- Project -[CREATED_BY]-> Person     (project.owner)
- KnowledgeCard -[MENTIONS]-> Person (card.people)
"""

from __future__ import annotations

from typing import Any

from app.graph.models import Edge, Node, node_id, slugify


def build(projects: list[dict[str, Any]], cards: list[dict[str, Any]]) -> tuple[list[Node], list[Edge]]:
    nodes: list[Node] = []
    edges: list[Edge] = []
    seen: set[str] = set()

    def person_node(name: str) -> str:
        pid = node_id("Person", slugify(name))
        if pid not in seen:
            seen.add(pid)
            nodes.append(Node(id=pid, type="Person", label=name, data={}))
        return pid

    for project in projects:
        owner = (project.get("owner") or "").strip()
        if owner:
            pid = person_node(owner)
            edges.append(Edge(source=node_id("Project", project["id"]), target=pid, type="CREATED_BY"))

    for card in cards:
        conv_id = card.get("conversation_id")
        if not conv_id:
            continue
        for name in card.get("people", []) or []:
            pid = person_node(name)
            edges.append(Edge(source=node_id("KnowledgeCard", conv_id), target=pid, type="MENTIONS"))

    return nodes, edges
