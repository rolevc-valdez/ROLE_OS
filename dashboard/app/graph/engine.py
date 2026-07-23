"""Graph Engine: assembles the full Knowledge Graph on demand.

Consumes three existing databases, read-only:
- Builder database (`app.db`)             -- knowledge cards
- Project Intelligence database (`app.projects.db`) -- projects, workspaces,
  capabilities, dependencies
- Advisor database (`app.advisor.db`)     -- recommendations (used by impact
  analysis, not by graph construction itself)

No data duplication: nothing here is persisted to a new SQLite file. Every
call to `build_graph()` reads the current state of the three databases and
computes a fresh in-memory `Graph`. This mirrors the recompute-on-read
pattern the Advisor (Epic 2) uses for recommendations.
"""

from __future__ import annotations

from app import db as knowledge_db
from app.config import Settings, get_settings
from app.graph.builders import (
    application_graph,
    capability_graph,
    dependency_graph,
    knowledge_graph,
    people_graph,
    project_graph,
    vendor_graph,
)
from app.graph.models import Graph
from app.projects import db as projects_db


def _load_projects(settings: Settings) -> list[dict]:
    return projects_db.list_projects(settings=settings)


def _load_workspaces(settings: Settings) -> list[dict]:
    return projects_db.list_workspaces(settings=settings)


def _load_cards(settings: Settings) -> list[dict]:
    if not knowledge_db.database_exists(settings):
        return []
    return knowledge_db.list_all_cards(settings=settings)


def _load_capabilities_and_consumers(settings: Settings) -> tuple[list[dict], dict[str, list[dict]]]:
    capabilities = projects_db.list_capabilities(settings=settings)
    consumers_by_capability: dict[str, list[dict]] = {}
    for cap in capabilities:
        consumers_by_capability[cap["id"]] = projects_db.list_capability_consumers(cap["id"], settings=settings)
    return capabilities, consumers_by_capability


def _load_dependencies(projects: list[dict], settings: Settings) -> list[dict]:
    all_deps: list[dict] = []
    for project in projects:
        all_deps.extend(projects_db.list_dependencies(project["id"], settings=settings))
    return all_deps


def build_graph(settings: Settings | None = None) -> Graph:
    """Build the full Knowledge Graph from current database state."""
    settings = settings or get_settings()

    projects = _load_projects(settings)
    workspaces = _load_workspaces(settings)
    cards = _load_cards(settings)
    capabilities, consumers_by_capability = _load_capabilities_and_consumers(settings)
    dependencies = _load_dependencies(projects, settings)

    contributions = [
        project_graph.build(projects, workspaces),
        dependency_graph.build(dependencies),
        capability_graph.build(capabilities, consumers_by_capability),
        knowledge_graph.build(cards, projects),
        people_graph.build(projects, cards),
        application_graph.build(cards, projects),
        vendor_graph.build(cards, projects),
    ]

    graph = Graph()
    # Add every node from every builder first, so that edges referencing a
    # node contributed by a *different* builder (e.g. vendor_graph's
    # PROVIDES edges pointing at Application nodes owned by
    # application_graph) are never dropped because their target hadn't been
    # added yet.
    for nodes, _edges in contributions:
        for node in nodes:
            graph.add_node(node)
    for _nodes, edges in contributions:
        for edge in edges:
            graph.add_edge(edge)

    return graph
