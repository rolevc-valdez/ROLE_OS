"""Pydantic request/response schemas for the Knowledge Graph API (Sprint 5)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class NodeOut(BaseModel):
    id: str
    type: str
    label: str
    data: dict[str, Any] = Field(default_factory=dict)


class EdgeOut(BaseModel):
    source: str
    target: str
    type: str


class GraphMetrics(BaseModel):
    nodes: int
    edges: int


class GraphOut(BaseModel):
    nodes: list[NodeOut]
    edges: list[EdgeOut]
    metrics: GraphMetrics


class NodeDetail(BaseModel):
    node: NodeOut
    edges: list[EdgeOut]


class NeighborEntry(BaseModel):
    node: NodeOut
    edge: EdgeOut
