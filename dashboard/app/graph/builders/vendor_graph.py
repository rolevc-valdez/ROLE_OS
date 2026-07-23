"""Builds Vendor nodes, deduplicated by name:

- KnowledgeCard -[MENTIONS]-> Vendor
- Project -[USES]-> Vendor        (aggregated, same pattern as
  application_graph.py)
- Vendor -[PROVIDES]-> Application (deterministic co-occurrence signal: if a
  vendor and an application are mentioned together in the same card at
  least once, the vendor is inferred to provide that application. No
  randomness -- purely a count over real data.)
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

    def vendor_node(name: str) -> str:
        vid = node_id("Vendor", slugify(name))
        if vid not in seen:
            seen.add(vid)
            nodes.append(Node(id=vid, type="Vendor", label=name, data={}))
        return vid

    project_vendor_pairs: set[tuple[str, str]] = set()
    provides_pairs: set[tuple[str, str]] = set()

    for card in cards:
        conv_id = card.get("conversation_id")
        if not conv_id:
            continue
        card_nid = node_id("KnowledgeCard", conv_id)
        vendors = card.get("vendors", []) or []
        applications = card.get("applications", []) or []

        for vendor_name in vendors:
            vid = vendor_node(vendor_name)
            edges.append(Edge(source=card_nid, target=vid, type="MENTIONS"))
            project = conversation_to_project.get(conv_id)
            if project:
                pair = (project["id"], vid)
                if pair not in project_vendor_pairs:
                    project_vendor_pairs.add(pair)
                    edges.append(Edge(source=node_id("Project", project["id"]), target=vid, type="USES"))

            for app_name in applications:
                aid = node_id("Application", slugify(app_name))
                key = (vid, aid)
                if key not in provides_pairs:
                    provides_pairs.add(key)
                    edges.append(Edge(source=vid, target=aid, type="PROVIDES", data={"basis": "co-occurrence"}))

    return nodes, edges
