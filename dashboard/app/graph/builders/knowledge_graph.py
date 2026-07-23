"""Builds KnowledgeCard and Conversation nodes from the Builder database.

- KnowledgeCard -[GENERATED_FROM]-> Conversation   (the card is the processed
  artifact; the Conversation node represents the raw underlying chat it was
  generated from)
- KnowledgeCard -[RELATED_TO]-> KnowledgeCard       (related_conversations,
  computed by builder/extractors/relationships.py in Milestone 3)
- KnowledgeCard -[BELONGS_TO]-> Project             (when the card's
  conversation_id is linked to a Project Intelligence project via
  `project.conversations`)
- KnowledgeCard -[REFERENCES]-> Asset               (files mentioned in the
  conversation, distinct from a Project's own curated `assets` collection)
"""

from __future__ import annotations

from typing import Any

from app.graph.models import Edge, Node, node_id, slugify


def build(cards: list[dict[str, Any]], projects: list[dict[str, Any]]) -> tuple[list[Node], list[Edge]]:
    nodes: list[Node] = []
    edges: list[Edge] = []

    # conversation_id -> project (for BELONGS_TO)
    conversation_to_project: dict[str, dict[str, Any]] = {}
    for project in projects:
        for conv_id in project.get("conversations", []) or []:
            conversation_to_project[conv_id] = project

    for card in cards:
        conv_id = card.get("conversation_id")
        if not conv_id:
            continue
        card_nid = node_id("KnowledgeCard", conv_id)
        conv_nid = node_id("Conversation", conv_id)

        nodes.append(
            Node(
                id=card_nid,
                type="KnowledgeCard",
                label=card.get("title", conv_id),
                data={
                    "conversation_id": conv_id,
                    "project": card.get("project"),
                    "category": card.get("category"),
                    "status": card.get("status"),
                    "date": card.get("date"),
                    "summary": card.get("summary", ""),
                },
            )
        )
        nodes.append(
            Node(
                id=conv_nid,
                type="Conversation",
                label=card.get("title", conv_id),
                data={"conversation_id": conv_id, "date": card.get("date"), "updated": card.get("updated")},
            )
        )
        edges.append(Edge(source=card_nid, target=conv_nid, type="GENERATED_FROM"))

        for related_conv_id in card.get("related_conversations", []) or []:
            edges.append(Edge(source=card_nid, target=node_id("KnowledgeCard", related_conv_id), type="RELATED_TO"))

        project = conversation_to_project.get(conv_id)
        if project:
            edges.append(Edge(source=card_nid, target=node_id("Project", project["id"]), type="BELONGS_TO"))

        for filename in card.get("assets", []) or card.get("files", []) or []:
            asset_nid = node_id("Asset", f"file-{slugify(filename)}")
            nodes.append(Node(id=asset_nid, type="Asset", label=filename, data={"filename": filename, "source": "conversation"}))
            edges.append(Edge(source=card_nid, target=asset_nid, type="REFERENCES"))

    return nodes, edges
