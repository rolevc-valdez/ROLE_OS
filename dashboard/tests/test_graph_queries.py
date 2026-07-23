"""Traversal, pathfinding, impact analysis, search, and named
convenience-query tests, built against a small hand-assembled Graph so
these stay fast and don't depend on any database."""

from __future__ import annotations

from app.graph import queries
from app.graph.models import Edge, Graph, Node, node_id


def make_graph() -> Graph:
    """
    ROLE_MASTER --DEPENDS_ON--- (nothing) ; SUPER_FACIL --DEPENDS_ON--> ROLE_MASTER
    ROLE_MASTER --UNBLOCKS--> SUPER_FACIL (reverse, added by dependency_graph in real use)
    ROLE_MASTER --IMPLEMENTS--> Brand Identity (Capability)
    SUPER_FACIL --USES--> Brand Identity
    conv-1 (KnowledgeCard) --BELONGS_TO--> ROLE_MASTER
    conv-1 --MENTIONS--> Claude (Application)
    conv-1 --MENTIONS--> Ana (Person)
    """
    g = Graph()
    rm = node_id("Project", "p1")
    sf = node_id("Project", "p2")
    cap = node_id("Capability", "c1")
    card = node_id("KnowledgeCard", "conv-1")
    claude = node_id("Application", "claude")
    ana = node_id("Person", "ana")

    g.add_node(Node(id=rm, type="Project", label="ROLE MASTER", data={"project_id": "p1", "workspace": "Products"}))
    g.add_node(Node(id=sf, type="Project", label="SUPER FACIL", data={"project_id": "p2", "workspace": "Products"}))
    g.add_node(Node(id=cap, type="Capability", label="Brand Identity"))
    g.add_node(Node(id=card, type="KnowledgeCard", label="Master planning"))
    g.add_node(Node(id=claude, type="Application", label="Claude"))
    g.add_node(Node(id=ana, type="Person", label="Ana"))

    g.add_edge(Edge(source=sf, target=rm, type="DEPENDS_ON"))
    g.add_edge(Edge(source=rm, target=sf, type="UNBLOCKS"))
    g.add_edge(Edge(source=rm, target=cap, type="IMPLEMENTS"))
    g.add_edge(Edge(source=sf, target=cap, type="USES"))
    g.add_edge(Edge(source=card, target=rm, type="BELONGS_TO"))
    g.add_edge(Edge(source=card, target=claude, type="MENTIONS"))
    g.add_edge(Edge(source=card, target=ana, type="MENTIONS"))
    return g


def test_neighbors_respects_direction_and_depth():
    g = make_graph()
    rm = node_id("Project", "p1")
    out_only = queries.neighbors(g, rm, direction="out", depth=1)
    assert {e["node"]["label"] for e in out_only} == {"SUPER FACIL", "Brand Identity"}

    in_only = queries.neighbors(g, rm, direction="in", depth=1)
    assert {e["node"]["label"] for e in in_only} == {"SUPER FACIL", "Master planning"}


def test_neighbors_filters_by_edge_type_and_node_type():
    g = make_graph()
    rm = node_id("Project", "p1")
    caps = queries.neighbors(g, rm, direction="out", edge_type="IMPLEMENTS", node_type="Capability", depth=1)
    assert len(caps) == 1
    assert caps[0]["node"]["label"] == "Brand Identity"


def test_shortest_path_between_two_projects():
    g = make_graph()
    sf = node_id("Project", "p2")
    rm = node_id("Project", "p1")
    result = queries.shortest_path(g, sf, rm)
    assert result is not None
    assert [n["label"] for n in result["nodes"]] == ["SUPER FACIL", "ROLE MASTER"]
    assert result["edges"][0]["type"] == "DEPENDS_ON"


def test_shortest_path_returns_none_when_unreachable():
    g = make_graph()
    g.add_node(Node(id=node_id("Project", "isolated"), type="Project", label="Isolated"))
    result = queries.shortest_path(g, node_id("Project", "isolated"), node_id("Project", "p1"))
    assert result is None


def test_shortest_path_same_node_returns_single_node_path():
    g = make_graph()
    rm = node_id("Project", "p1")
    result = queries.shortest_path(g, rm, rm)
    assert [n["label"] for n in result["nodes"]] == ["ROLE MASTER"]
    assert result["edges"] == []


def test_search_nodes_matches_substring_case_insensitively():
    g = make_graph()
    results = queries.search_nodes(g, "role")
    assert any(r["label"] == "ROLE MASTER" for r in results)


def test_find_nodes_by_label_ranks_exact_matches_first():
    g = make_graph()
    matches = queries.find_nodes_by_label(g, "ROLE MASTER", node_type="Project")
    assert matches[0].label == "ROLE MASTER"


def test_projects_related_to_example_query():
    g = make_graph()
    related = queries.projects_related_to(g, "ROLE MASTER")
    assert any(e["node"]["label"] == "SUPER FACIL" for e in related)


def test_capabilities_used_by_example_query():
    g = make_graph()
    used = queries.capabilities_used_by(g, "SUPER FACIL")
    assert [e["node"]["label"] for e in used] == ["Brand Identity"]


def test_conversations_mentioning_example_query():
    g = make_graph()
    mentions = queries.conversations_mentioning(g, "Claude")
    assert [e["node"]["label"] for e in mentions] == ["Master planning"]


def test_people_involved_in_example_query():
    g = make_graph()
    people = queries.people_involved_in(g, "ROLE MASTER")
    assert any(e["node"]["label"] == "Ana" for e in people)


def test_projects_blocked_by_and_unlocked_by_finishing():
    g = make_graph()
    blocked = queries.projects_blocked_by(g, "ROLE MASTER")
    assert [e["node"]["label"] for e in blocked] == ["SUPER FACIL"]
    unlocked = queries.projects_unlocked_by_finishing(g, "ROLE MASTER")
    assert [e["node"]["label"] for e in unlocked] == ["SUPER FACIL"]


def test_impact_analysis_groups_by_type_and_looks_up_advisor(monkeypatch):
    g = make_graph()
    monkeypatch.setattr(
        "app.graph.queries.advisor_db.list_recommendations",
        lambda **kwargs: [{"id": "r1", "project_id": kwargs.get("project_id")}],
    )
    result = queries.impact_analysis(g, node_id("Project", "p1"), max_depth=3)
    assert result["origin"]["label"] == "ROLE MASTER"
    assert any(n["label"] == "SUPER FACIL" for n in result["affected_by_type"]["Project"])
    assert any(n["label"] == "Brand Identity" for n in result["affected_by_type"]["Capability"])
    assert result["advisor_recommendations"]


def test_impact_analysis_returns_none_for_unknown_node():
    g = make_graph()
    assert queries.impact_analysis(g, "project:does-not-exist") is None
