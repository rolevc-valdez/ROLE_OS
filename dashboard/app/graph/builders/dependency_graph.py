"""Builds Project<->Project dependency edges.

- Project -[DEPENDS_ON]-> Project     (A depends on B)
- Project -[UNBLOCKS]-> Project       (B unblocks A -- the reverse view,
  precomputed here as a convenience so "what does finishing this project
  unlock?" is a single outgoing-edge lookup instead of requiring callers to
  walk DEPENDS_ON backwards.)
"""

from __future__ import annotations

from typing import Any

from app.graph.models import Edge, node_id


def build(dependencies: list[dict[str, Any]]) -> tuple[list, list[Edge]]:
    """`dependencies` is a flat list of rows shaped like the `dependencies`
    table: {project_id, depends_on_project_id, note, ...}, collected across
    every project (see engine.py)."""
    edges: list[Edge] = []
    for dep in dependencies:
        dependent = node_id("Project", dep["project_id"])
        provider = node_id("Project", dep["depends_on_project_id"])
        edges.append(Edge(source=dependent, target=provider, type="DEPENDS_ON", data={"note": dep.get("note", "")}))
        edges.append(Edge(source=provider, target=dependent, type="UNBLOCKS", data={"note": dep.get("note", "")}))
    return [], edges
