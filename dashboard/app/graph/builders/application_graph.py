"""Builds Application nodes, deduplicated by name:

- KnowledgeCard -[MENTIONS]-> Application
- Project -[USES]-> Application   (aggregated: a project uses whatever
  applications are mentioned in the conversations linked to it)
"""

from __future__ import annotations

from typing import Any

from app.graph.models import Edge, Node, node_id, slugify


def build(cards: list[dict[str, Any]], projects: list[dict[str, Any]]) -> tuple[list[Node], list[Edge]]:
    nodes: list[Node] = []
    edges: list[Edge] = []
    seen: set[str] = set()

    conversation_to_project: dict[str, dict[str, Any]] = {}
    for project in projects:
        for conv_id in project.get("conversations", []) or []:
            conversation_to_project[conv_id] = project

    def app_node(name: str) -> str:
        aid = node_id("Application", slugify(name))
        if aid not in seen:
            seen.add(aid)
            nodes.append(Node(id=aid, type="Application", label=name, data={}))
        return aid

    project_app_pairs: set[tuple[str, str]] = set()

    for card in cards:
        conv_id = card.get("conversation_id")
        if not conv_id:
            continue
        card_nid = node_id("KnowledgeCard", conv_id)
        for app_name in card.get("applications", []) or []:
            aid = app_node(app_name)
            edges.append(Edge(source=card_nid, target=aid, type="MENTIONS"))
            project = conversation_to_project.get(conv_id)
            if project:
                pair = (project["id"], aid)
                if pair not in project_app_pairs:
                    project_app_pairs.add(pair)
                    edges.append(Edge(source=node_id("Project", project["id"]), target=aid, type="USES"))

    return nodes, edges
