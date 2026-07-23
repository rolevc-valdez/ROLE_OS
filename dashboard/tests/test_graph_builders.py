"""Unit tests for each `app.graph.builders.*` module in isolation, using
hand-crafted dicts shaped like the real DB rows rather than a live database.
"""

from __future__ import annotations

from app.graph.builders import (
    application_graph,
    capability_graph,
    dependency_graph,
    knowledge_graph,
    people_graph,
    project_graph,
    vendor_graph,
)
from app.graph.models import node_id


WORKSPACES = [{"id": "ws1", "name": "Products", "description": "", "project_count": 2}]

PROJECT_A = {
    "id": "p1",
    "name": "ROLE MASTER",
    "workspace": "Products",
    "status": "active",
    "priority": "high",
    "health_score": 80,
    "owner": "Rogelio",
    "tags": ["brand"],
    "related_projects": ["p2"],
    "conversations": ["conv-1"],
    "decisions": [{"id": "d1", "text": "Use Claude", "created_at": "t"}],
    "deliverables": [{"id": "dl1", "text": "Brand kit", "created_at": "t"}],
    "prompts": [{"id": "pr1", "text": "Design the logo", "created_at": "t"}],
    "assets": [{"id": "a1", "name": "logo.png", "created_at": "t"}],
}

PROJECT_B = {
    "id": "p2",
    "name": "SUPER FACIL",
    "workspace": "Products",
    "status": "active",
    "priority": "medium",
    "health_score": 60,
    "owner": "Rogelio",
    "tags": [],
    "related_projects": [],
    "conversations": [],
    "decisions": [],
    "deliverables": [],
    "prompts": [],
    "assets": [],
}


def test_project_graph_builds_projects_workspaces_and_references():
    nodes, edges = project_graph.build([PROJECT_A, PROJECT_B], WORKSPACES)
    node_types = {n.type for n in nodes}
    assert {"Project", "Workspace", "Decision", "Deliverable", "Prompt", "Asset"} <= node_types

    edge_types = {e.type for e in edges}
    assert "BELONGS_TO" in edge_types
    assert "RELATED_TO" in edge_types
    assert "REFERENCES" in edge_types

    related_edges = [e for e in edges if e.type == "RELATED_TO"]
    assert related_edges[0].source == node_id("Project", "p1")
    assert related_edges[0].target == node_id("Project", "p2")


def test_dependency_graph_builds_depends_on_and_reverse_unblocks():
    deps = [{"project_id": "p2", "depends_on_project_id": "p1", "note": "needs brand"}]
    nodes, edges = dependency_graph.build(deps)
    assert nodes == []
    by_type = {e.type: e for e in edges}
    assert by_type["DEPENDS_ON"].source == node_id("Project", "p2")
    assert by_type["DEPENDS_ON"].target == node_id("Project", "p1")
    assert by_type["UNBLOCKS"].source == node_id("Project", "p1")
    assert by_type["UNBLOCKS"].target == node_id("Project", "p2")


def test_capability_graph_builds_implements_uses_and_shares():
    capabilities = [{"id": "c1", "project_id": "p1", "name": "Brand Identity", "description": "", "category": ""}]
    consumers = {"c1": [{"consumer_project_id": "p2"}]}
    nodes, edges = capability_graph.build(capabilities, consumers)
    assert nodes[0].type == "Capability"
    edge_types = [e.type for e in edges]
    assert "IMPLEMENTS" in edge_types
    assert "USES" in edge_types
    assert "SHARES_CAPABILITY" in edge_types


CARD = {
    "conversation_id": "conv-1",
    "title": "ROLE Master planning",
    "project": "ROLE_MASTER",
    "category": "PROJECT",
    "status": "Completed",
    "date": "2026-01-01",
    "summary": "Plan the brand kit",
    "people": ["Rogelio Valdez"],
    "applications": ["Claude"],
    "vendors": ["Anthropic"],
    "assets": ["brand.png"],
    "related_conversations": ["conv-2"],
}

CARD_2 = {**CARD, "conversation_id": "conv-2", "title": "Follow-up", "related_conversations": []}


def test_knowledge_graph_builds_cards_conversations_and_links():
    nodes, edges = knowledge_graph.build([CARD, CARD_2], [PROJECT_A])
    node_types = {n.type for n in nodes}
    assert {"KnowledgeCard", "Conversation", "Asset"} <= node_types

    edge_types = {e.type for e in edges}
    assert "GENERATED_FROM" in edge_types
    assert "RELATED_TO" in edge_types
    assert "BELONGS_TO" in edge_types
    assert "REFERENCES" in edge_types

    belongs = [e for e in edges if e.type == "BELONGS_TO"]
    assert belongs[0].source == node_id("KnowledgeCard", "conv-1")
    assert belongs[0].target == node_id("Project", "p1")


def test_people_graph_dedupes_person_nodes_across_sources():
    nodes, edges = people_graph.build([PROJECT_A], [CARD])
    person_nodes = [n for n in nodes if n.type == "Person"]
    # "Rogelio" (owner) and "Rogelio Valdez" (card mention) are different
    # strings so they are NOT expected to collapse into one node -- but
    # each name should only ever produce a single node even if mentioned
    # multiple times.
    labels = [n.label for n in person_nodes]
    assert len(labels) == len(set(labels))
    edge_types = {e.type for e in edges}
    assert "CREATED_BY" in edge_types
    assert "MENTIONS" in edge_types


def test_application_graph_mentions_and_aggregated_project_use():
    nodes, edges = application_graph.build([CARD], [PROJECT_A])
    assert any(n.type == "Application" and n.label == "Claude" for n in nodes)
    edge_types = {e.type for e in edges}
    assert "MENTIONS" in edge_types
    assert "USES" in edge_types


def test_vendor_graph_mentions_uses_and_provides_by_cooccurrence():
    nodes, edges = vendor_graph.build([CARD], [PROJECT_A])
    assert any(n.type == "Vendor" and n.label == "Anthropic" for n in nodes)
    provides = [e for e in edges if e.type == "PROVIDES"]
    assert len(provides) == 1
    assert provides[0].source == node_id("Vendor", "anthropic")
    assert provides[0].target == node_id("Application", "claude")
