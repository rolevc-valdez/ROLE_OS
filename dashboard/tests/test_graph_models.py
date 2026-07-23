"""Unit tests for the core Node/Edge/Graph data structures."""

from __future__ import annotations

import pytest

from app.graph.models import Edge, Graph, Node, node_id, slugify


def test_node_id_is_stable_and_type_prefixed():
    assert node_id("Project", "abc123") == "project:abc123"
    assert node_id("Person", "juan-perez") == "person:juan-perez"


def test_slugify_normalizes_and_dedupes_names():
    assert slugify("Microsoft") == slugify("  microsoft  ")
    assert slugify("Master Factory") == "master-factory"
    assert slugify("") == "unknown"


def test_node_rejects_unknown_type():
    with pytest.raises(ValueError):
        Node(id="x:1", type="NotARealType", label="x")


def test_edge_rejects_unknown_relationship_type():
    with pytest.raises(ValueError):
        Edge(source="a", target="b", type="NOT_A_REAL_RELATIONSHIP")


def test_graph_add_node_merges_data_on_duplicate_id():
    graph = Graph()
    graph.add_node(Node(id="person:juan", type="Person", label="Juan", data={"role": "owner"}))
    graph.add_node(Node(id="person:juan", type="Person", label="Juan", data={"team": "core"}))
    node = graph.get_node("person:juan")
    assert node.data == {"role": "owner", "team": "core"}
    assert len(graph) == 1


def test_graph_add_edge_dropped_if_endpoints_missing():
    graph = Graph()
    graph.add_node(Node(id="project:a", type="Project", label="A"))
    # target "project:b" was never added -- edge should be silently skipped.
    graph.add_edge(Edge(source="project:a", target="project:b", type="DEPENDS_ON"))
    assert graph.edges == []


def test_graph_edges_from_to_and_touching():
    graph = Graph()
    graph.add_node(Node(id="project:a", type="Project", label="A"))
    graph.add_node(Node(id="project:b", type="Project", label="B"))
    graph.add_edge(Edge(source="project:a", target="project:b", type="DEPENDS_ON"))

    assert len(graph.edges_from("project:a")) == 1
    assert len(graph.edges_to("project:b")) == 1
    assert len(graph.edges_touching("project:a")) == 1
    assert len(graph.edges_touching("project:b")) == 1
    assert graph.edges_from("project:b") == []


def test_graph_to_dict_shape():
    graph = Graph()
    graph.add_node(Node(id="project:a", type="Project", label="A", data={"status": "active"}))
    out = graph.to_dict()
    assert out["nodes"] == [{"id": "project:a", "type": "Project", "label": "A", "data": {"status": "active"}}]
    assert out["edges"] == []
