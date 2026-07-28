"""Knowledge Graph API (Sprint 5), namespaced under /conversation-graph.

Independent of the Epic 3 `/graph` API -- see
`app/conversation_graph/__init__.py` for why. The graph is rebuilt fresh
from the imports and extraction databases on every request; there is no
dedicated graph database.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import Settings, get_settings
from app.conversation_graph.api_models import GraphMetrics, GraphOut, NeighborEntry, NodeDetail, NodeOut
from app.conversation_graph.engine import build_graph
from app.conversation_graph.models import NODE_TYPES, node_id

router = APIRouter(prefix="/conversation-graph", tags=["conversation-graph"])


def _filtered_graph(graph, conversation_id: str | None, node_type: str | None):
    nodes = graph.nodes
    if conversation_id:
        cid = node_id("conversation", conversation_id)
        if not graph.has_node(cid):
            return [], []
        keep_ids = {cid} | {n.id for n, _ in graph.neighbors(cid)}
        nodes = [n for n in nodes if n.id in keep_ids]
    if node_type:
        nodes = [n for n in nodes if n.type == node_type]
    node_ids = {n.id for n in nodes}
    edges = [e for e in graph.edges if e.source in node_ids and e.target in node_ids]
    return nodes, edges


@router.get("", response_model=GraphOut)
def get_graph(
    conversation_id: str | None = Query(None, description="Filter to one conversation and its contained objects"),
    node_type: str | None = Query(None, description="Filter to one node type"),
    settings: Settings = Depends(get_settings),
) -> GraphOut:
    if node_type is not None and node_type not in NODE_TYPES:
        raise HTTPException(status_code=400, detail=f"node_type must be one of {NODE_TYPES}")
    graph = build_graph(settings)
    nodes, edges = _filtered_graph(graph, conversation_id, node_type)
    return GraphOut(
        nodes=[NodeOut(**n.to_dict()) for n in nodes],
        edges=[e.to_dict() for e in edges],
        metrics=GraphMetrics(nodes=len(nodes), edges=len(edges)),
    )


@router.get("/nodes/{node_id}", response_model=NodeDetail)
def get_node(node_id: str, settings: Settings = Depends(get_settings)) -> NodeDetail:
    graph = build_graph(settings)
    node = graph.get_node(node_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")
    edges = [e.to_dict() for e in graph.edges_touching(node_id)]
    return NodeDetail(node=NodeOut(**node.to_dict()), edges=edges)


@router.get("/nodes/{node_id}/neighbors", response_model=list[NeighborEntry])
def get_neighbors(node_id: str, settings: Settings = Depends(get_settings)) -> list[NeighborEntry]:
    graph = build_graph(settings)
    if not graph.has_node(node_id):
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")
    return [
        NeighborEntry(node=NodeOut(**n.to_dict()), edge=e.to_dict())
        for n, e in graph.neighbors(node_id)
    ]
