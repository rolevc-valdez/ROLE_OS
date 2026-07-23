"""Knowledge Graph API (Epic 3).

Namespaced under `/graph`, entirely additive -- no existing route from
Milestones 1-2 or Epics 1-2 is touched. The graph is rebuilt fresh on every
request from the three existing databases (see `app.graph.engine`); there
is no dedicated graph database.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import Settings, get_settings
from app.graph import queries
from app.graph.api_models import GraphOut, ImpactResult, NeighborEntry, NodeOut, PathResult
from app.graph.engine import build_graph
from app.graph.models import NODE_TYPES, RELATIONSHIP_TYPES

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("", response_model=GraphOut)
def get_graph(
    node_type: str | None = Query(None),
    workspace: str | None = Query(None),
    settings: Settings = Depends(get_settings),
) -> GraphOut:
    graph = build_graph(settings)
    nodes = graph.nodes
    if node_type:
        nodes = [n for n in nodes if n.type == node_type]
    if workspace:
        def in_workspace(n):
            if n.type == "Workspace":
                return n.label == workspace
            return n.data.get("workspace") == workspace
        nodes = [n for n in nodes if in_workspace(n)]
    node_ids = {n.id for n in nodes}
    edges = [e for e in graph.edges if e.source in node_ids and e.target in node_ids]
    return GraphOut(nodes=[NodeOut(**n.to_dict()) for n in nodes], edges=[e.to_dict() for e in edges])


@router.get("/project/{project_id}", response_model=GraphOut)
def get_project_subgraph(
    project_id: str, depth: int = Query(1, ge=1, le=5), settings: Settings = Depends(get_settings)
) -> GraphOut:
    graph = build_graph(settings)
    from app.graph.models import node_id as make_id

    pid = make_id("Project", project_id)
    if not graph.has_node(pid):
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found in graph")

    entries = queries.neighbors(graph, pid, direction="both", depth=depth)
    node_map = {pid: graph.get_node(pid)}
    edges = []
    for entry in entries:
        node_map[entry["node"]["id"]] = graph.get_node(entry["node"]["id"])
        edges.append(entry["edge"])
    return GraphOut(
        nodes=[NodeOut(**n.to_dict()) for n in node_map.values() if n],
        edges=edges,
    )


@router.get("/node/{node_id}", response_model=dict)
def get_node(node_id: str, settings: Settings = Depends(get_settings)) -> dict:
    graph = build_graph(settings)
    node = graph.get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")
    edges = [e.to_dict() for e in graph.edges_touching(node_id)]
    return {"node": node.to_dict(), "edges": edges}


@router.get("/neighbors/{node_id}", response_model=list[NeighborEntry])
def get_neighbors(
    node_id: str,
    direction: str = Query("both", pattern="^(out|in|both)$"),
    edge_type: str | None = Query(None),
    node_type: str | None = Query(None),
    depth: int = Query(1, ge=1, le=6),
    settings: Settings = Depends(get_settings),
) -> list[NeighborEntry]:
    graph = build_graph(settings)
    if not graph.has_node(node_id):
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")
    entries = queries.neighbors(
        graph, node_id, direction=direction, edge_type=edge_type, node_type=node_type, depth=depth
    )
    return [NeighborEntry(**e) for e in entries]


@router.get("/path", response_model=PathResult)
def get_path(
    source: str = Query(...),
    target: str = Query(...),
    max_depth: int = Query(8, ge=1, le=20),
    settings: Settings = Depends(get_settings),
) -> PathResult:
    graph = build_graph(settings)
    if not graph.has_node(source) or not graph.has_node(target):
        raise HTTPException(status_code=404, detail="Source or target node not found")
    result = queries.shortest_path(graph, source, target, max_depth=max_depth)
    if result is None:
        return PathResult(found=False)
    return PathResult(found=True, nodes=result["nodes"], edges=result["edges"])


@router.get("/impact/{node_id}", response_model=ImpactResult)
def get_impact(
    node_id: str, max_depth: int = Query(4, ge=1, le=10), settings: Settings = Depends(get_settings)
) -> ImpactResult:
    graph = build_graph(settings)
    result = queries.impact_analysis(graph, node_id, max_depth=max_depth, settings=settings)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")
    return ImpactResult(**result)


@router.get("/search", response_model=list[NodeOut])
def search(
    q: str = Query(""),
    node_type: str | None = Query(None),
    workspace: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    settings: Settings = Depends(get_settings),
) -> list[NodeOut]:
    graph = build_graph(settings)
    results = queries.search_nodes(graph, q, node_type=node_type, workspace=workspace, limit=limit)
    return [NodeOut(**r) for r in results]


@router.get("/meta/types", response_model=dict)
def get_meta_types() -> dict:
    """Small convenience endpoint listing the fixed node/relationship
    vocabularies, used by the dashboard's filter dropdowns."""
    return {"node_types": list(NODE_TYPES), "relationship_types": list(RELATIONSHIP_TYPES)}
