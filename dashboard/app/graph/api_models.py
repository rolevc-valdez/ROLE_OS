"""Pydantic response schemas for the Graph API (`/graph/*`)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class NodeOut(BaseModel):
    id: str
    type: str
    label: str
    data: dict[str, Any] = {}

    model_config = ConfigDict(extra="ignore")


class EdgeOut(BaseModel):
    source: str
    target: str
    type: str
    data: dict[str, Any] = {}

    model_config = ConfigDict(extra="ignore")


class GraphOut(BaseModel):
    nodes: list[NodeOut]
    edges: list[EdgeOut]


class NeighborEntry(BaseModel):
    node: NodeOut
    edge: EdgeOut
    distance: int


class PathResult(BaseModel):
    found: bool
    nodes: list[NodeOut] = []
    edges: list[EdgeOut] = []


class ImpactResult(BaseModel):
    origin: NodeOut | None
    affected_by_type: dict[str, list[NodeOut]]
    advisor_recommendations: list[dict[str, Any]]
    total_affected: int
