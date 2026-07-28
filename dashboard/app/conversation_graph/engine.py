"""Builds the Sprint 5 Knowledge Graph on demand from the imports and
extraction databases -- no dedicated graph database, same "recompute
every request" philosophy as the Epic 3 Knowledge Graph engine.
"""

from __future__ import annotations

from app.config import Settings, get_settings
from app.conversation_graph.models import Edge, Graph, Node, node_id
from app.extraction import db as extraction_db
from app.imports import db as imports_db

# Extraction's capitalized object_type -> this domain's lowercase node type.
_OBJECT_TYPE_TO_NODE_TYPE = {
    "Project": "project",
    "Person": "person",
    "Task": "task",
    "Decision": "decision",
    "Idea": "idea",
    "Document": "document",
    "Asset": "asset",
}


def build_graph(settings: Settings | None = None) -> Graph:
    """Build the full graph: one node per imported conversation, one node
    per extracted knowledge object, and a `contains` edge from each
    conversation to every object extracted from it.

    Safe against partial/inconsistent data: an extracted object whose
    source conversation no longer exists (deleted) still becomes a node,
    it just ends up with no edge pointing to it -- `Graph.add_edge` drops
    edges referencing a missing node rather than raising.
    """
    settings = settings or get_settings()
    graph = Graph()

    conversations = imports_db.list_conversations(settings=settings, limit=100_000)
    for conv in conversations:
        cid = node_id("conversation", conv["id"])
        graph.add_node(
            Node(
                id=cid,
                type="conversation",
                label=conv.get("title") or "Untitled conversation",
                data={
                    "conversation_id": conv["id"],
                    "source": conv.get("source"),
                    "created_at": conv.get("created_at"),
                    "updated_at": conv.get("updated_at"),
                    "message_count": conv.get("message_count", 0),
                },
            )
        )

    objects = extraction_db.list_all_objects(settings=settings)
    for obj in objects:
        node_type = _OBJECT_TYPE_TO_NODE_TYPE.get(obj["object_type"])
        if node_type is None:
            continue  # defensive: an unsupported type should never crash graph construction
        oid = node_id(node_type, obj["id"])
        graph.add_node(
            Node(
                id=oid,
                type=node_type,
                label=obj.get("title") or "Untitled",
                data={
                    "conversation_id": obj.get("conversation_id"),
                    "confidence": obj.get("confidence"),
                    "source": obj.get("source"),
                    "created_at": obj.get("created_at"),
                    "updated_at": obj.get("updated_at"),
                },
            )
        )
        conversation_node_id = node_id("conversation", obj.get("conversation_id") or "")
        graph.add_edge(Edge(source=conversation_node_id, target=oid, type="contains"))

    return graph
