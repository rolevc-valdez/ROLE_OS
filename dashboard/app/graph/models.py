"""Core graph data structures: Node, Edge, and the Graph container.

Everything here is plain, dependency-free Python so the Knowledge Graph
engine can be imported and used headlessly -- from tests, from a future AI
provider, or from the dashboard API -- without any web/UI code involved.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

# ---------------------------------------------------------------------------
# Node types (exactly 12, per Epic 3 spec)
# ---------------------------------------------------------------------------

NODE_TYPES = (
    "Project",
    "KnowledgeCard",
    "Person",
    "Application",
    "Vendor",
    "Capability",
    "Workspace",
    "Decision",
    "Deliverable",
    "Prompt",
    "Asset",
    "Conversation",
)

# ---------------------------------------------------------------------------
# Relationship types (exactly 12, per Epic 3 spec)
# ---------------------------------------------------------------------------

RELATIONSHIP_TYPES = (
    "DEPENDS_ON",
    "PROVIDES",
    "USES",
    "REFERENCES",
    "RELATED_TO",
    "BELONGS_TO",
    "CREATED_BY",
    "MENTIONS",
    "GENERATED_FROM",
    "UNBLOCKS",
    "IMPLEMENTS",
    "SHARES_CAPABILITY",
)


def slugify(value: str) -> str:
    """Deterministic slug used to dedupe entity nodes (Person/Application/
    Vendor/Asset) that are referenced by name from multiple sources."""
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")
    return slug or "unknown"


def node_id(node_type: str, raw_id: str) -> str:
    """Build a globally unique, stable node id: '<type-lower>:<raw-id>'."""
    return f"{node_type.lower()}:{raw_id}"


@dataclass
class Node:
    id: str
    type: str
    label: str
    data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.type not in NODE_TYPES:
            raise ValueError(f"Unknown node type: {self.type}")

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "type": self.type, "label": self.label, "data": self.data}


@dataclass
class Edge:
    source: str
    target: str
    type: str
    data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.type not in RELATIONSHIP_TYPES:
            raise ValueError(f"Unknown relationship type: {self.type}")

    def to_dict(self) -> dict[str, Any]:
        return {"source": self.source, "target": self.target, "type": self.type, "data": self.data}


class Graph:
    """An in-memory, read-only-once-built collection of nodes and edges.

    Builders contribute `(nodes, edges)` tuples; the engine merges them here.
    Nodes are deduplicated by id (last write wins for data, but callers are
    expected to only add a given entity node once per build). Edges are kept
    as a flat list with an adjacency index built lazily for traversal.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, Node] = {}
        self._edges: list[Edge] = []
        self._out: dict[str, list[int]] = {}
        self._in: dict[str, list[int]] = {}

    def add_node(self, node: Node) -> None:
        if node.id in self._nodes:
            # Merge data from a second contribution rather than overwrite,
            # so e.g. a Person mentioned by multiple cards keeps accumulating
            # context instead of losing it.
            existing = self._nodes[node.id]
            existing.data.update({k: v for k, v in node.data.items() if k not in existing.data})
        else:
            self._nodes[node.id] = node

    def add_edge(self, edge: Edge) -> None:
        # Skip edges that reference nodes we don't have (defensive: keeps the
        # graph consistent even if a builder runs into partial/missing data).
        if edge.source not in self._nodes or edge.target not in self._nodes:
            return
        idx = len(self._edges)
        self._edges.append(edge)
        self._out.setdefault(edge.source, []).append(idx)
        self._in.setdefault(edge.target, []).append(idx)

    def extend(self, nodes: Iterable[Node], edges: Iterable[Edge]) -> None:
        for n in nodes:
            self.add_node(n)
        for e in edges:
            self.add_edge(e)

    @property
    def nodes(self) -> list[Node]:
        return list(self._nodes.values())

    @property
    def edges(self) -> list[Edge]:
        return list(self._edges)

    def get_node(self, node_id_: str) -> Node | None:
        return self._nodes.get(node_id_)

    def has_node(self, node_id_: str) -> bool:
        return node_id_ in self._nodes

    def edges_from(self, node_id_: str) -> list[Edge]:
        return [self._edges[i] for i in self._out.get(node_id_, [])]

    def edges_to(self, node_id_: str) -> list[Edge]:
        return [self._edges[i] for i in self._in.get(node_id_, [])]

    def edges_touching(self, node_id_: str) -> list[Edge]:
        return self.edges_from(node_id_) + self.edges_to(node_id_)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
        }

    def __len__(self) -> int:
        return len(self._nodes)
