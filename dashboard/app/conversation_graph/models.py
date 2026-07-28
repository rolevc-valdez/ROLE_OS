"""Core graph data structures for the Sprint 5 Knowledge Graph: Node, Edge,
and the Graph container. Plain, dependency-free Python, importable and
testable without any web/UI code involved -- same shape philosophy as
`app/graph/models.py`, but with this domain's own, much smaller vocabulary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

# Exactly these 8 node types are supported -- no more.
NODE_TYPES = (
    "conversation",
    "project",
    "person",
    "task",
    "decision",
    "idea",
    "document",
    "asset",
)

# Exactly one relationship type for v1.0: a conversation contains a
# knowledge object extracted from it. No inferred relationships between
# extracted objects themselves.
RELATIONSHIP_TYPES = ("contains",)


def node_id(node_type: str, raw_id: str) -> str:
    """Build a stable, globally unique node id: '<type>:<raw-id>'."""
    return f"{node_type}:{raw_id}"


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

    def __post_init__(self) -> None:
        if self.type not in RELATIONSHIP_TYPES:
            raise ValueError(f"Unknown relationship type: {self.type}")

    def to_dict(self) -> dict[str, Any]:
        return {"source": self.source, "target": self.target, "type": self.type}


class Graph:
    """An in-memory, built-once collection of nodes and edges.

    Nodes are deduplicated by id. Edges are deduplicated by
    (source, target, type) so the same conversation/object pair is never
    linked twice. Edges referencing a node that doesn't exist are silently
    dropped rather than raising -- this is what makes an orphaned extracted
    object (source conversation deleted) safe: the object still appears as
    a node, it just has no `contains` edge pointing to it.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, Node] = {}
        self._edge_keys: set[tuple[str, str, str]] = set()
        self._edges: list[Edge] = []
        self._out: dict[str, list[int]] = {}
        self._in: dict[str, list[int]] = {}

    def add_node(self, node: Node) -> None:
        self._nodes.setdefault(node.id, node)

    def add_edge(self, edge: Edge) -> None:
        if edge.source not in self._nodes or edge.target not in self._nodes:
            return
        key = (edge.source, edge.target, edge.type)
        if key in self._edge_keys:
            return
        self._edge_keys.add(key)
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

    def edges_touching(self, node_id_: str) -> list[Edge]:
        return [self._edges[i] for i in self._out.get(node_id_, [])] + [
            self._edges[i] for i in self._in.get(node_id_, [])
        ]

    def neighbors(self, node_id_: str) -> list[tuple[Node, Edge]]:
        """One-hop connected nodes for `node_id_`, each paired with the
        edge that connects them."""
        result: list[tuple[Node, Edge]] = []
        for edge in self.edges_touching(node_id_):
            other_id = edge.target if edge.source == node_id_ else edge.source
            other = self._nodes.get(other_id)
            if other is not None:
                result.append((other, edge))
        return result

    def __len__(self) -> int:
        return len(self._nodes)
