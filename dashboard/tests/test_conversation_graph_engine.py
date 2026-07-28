"""Unit tests for the Sprint 5 Knowledge Graph engine: graph construction,
supported node types, "contains" relationships, duplicate-edge prevention,
and behavior on empty/orphaned/incomplete data.
"""

from __future__ import annotations

import json
import uuid

from app.conversation_graph.engine import build_graph
from app.conversation_graph.models import NODE_TYPES, RELATIONSHIP_TYPES, Edge, Graph, Node, node_id
from app.extraction.service import run_extraction
from app.imports.service import run_import


def unique_id() -> str:
    return f"conv-{uuid.uuid4().hex[:8]}"


def import_one(text: str, conv_id: str | None = None) -> str:
    conv_id = conv_id or unique_id()
    payload = json.dumps(
        [
            {
                "id": conv_id,
                "title": f"Graph test {conv_id}",
                "create_time": 1700000000,
                "update_time": 1700003600,
                "mapping": {
                    "n1": {
                        "message": {
                            "author": {"role": "user"},
                            "create_time": 1700000000,
                            "content": {"parts": [text]},
                        }
                    }
                },
            }
        ]
    ).encode("utf-8")
    result = run_import(payload, "export.json")
    assert result["imported"] == 1

    from app.imports import db as imports_db

    matches = [c for c in imports_db.list_conversations(limit=500) if c["external_id"] == conv_id]
    return matches[0]["id"]


# ---------------------------------------------------------------------------
# Models: node/edge validation, duplicate-edge prevention
# ---------------------------------------------------------------------------


def test_only_eight_node_types_supported():
    assert set(NODE_TYPES) == {
        "conversation", "project", "person", "task", "decision", "idea", "document", "asset",
    }


def test_only_contains_relationship_supported():
    assert RELATIONSHIP_TYPES == ("contains",)


def test_node_rejects_unknown_type():
    try:
        Node(id="x:1", type="not-a-type", label="x")
        assert False, "should have raised"
    except ValueError:
        pass


def test_edge_rejects_unknown_type():
    try:
        Edge(source="a", target="b", type="not-a-relationship")
        assert False, "should have raised"
    except ValueError:
        pass


def test_graph_dedupes_identical_edges():
    g = Graph()
    g.add_node(Node(id="conversation:1", type="conversation", label="C"))
    g.add_node(Node(id="decision:1", type="decision", label="D"))
    edge = Edge(source="conversation:1", target="decision:1", type="contains")
    g.add_edge(edge)
    g.add_edge(Edge(source="conversation:1", target="decision:1", type="contains"))
    g.add_edge(Edge(source="conversation:1", target="decision:1", type="contains"))
    assert len(g.edges) == 1


def test_graph_drops_edges_referencing_missing_nodes():
    g = Graph()
    g.add_node(Node(id="conversation:1", type="conversation", label="C"))
    g.add_edge(Edge(source="conversation:1", target="decision:missing", type="contains"))
    assert len(g.edges) == 0


# ---------------------------------------------------------------------------
# Engine: full graph construction from real imports/extraction data
# ---------------------------------------------------------------------------


def test_build_graph_creates_conversation_node():
    conv_id = import_one("hello world, nothing extractable here")
    graph = build_graph()
    cid = node_id("conversation", conv_id)
    assert graph.has_node(cid)
    node = graph.get_node(cid)
    assert node.type == "conversation"
    assert node.data["message_count"] >= 1


def test_build_graph_creates_object_nodes_and_contains_edges():
    text = (
        "Necesitamos definir el proyecto de expansion antes del viernes.\n"
        "Maria Gonzalez va a liderar el equipo.\n"
        "Decidimos usar Claude para el pipeline. Aprobado por todos.\n"
        "Se me ocurre una idea: podriamos automatizar el reporte semanal.\n"
        "Todavia esta pendiente revisar el presupuesto.\n"
        "Adjunto budget_report.pdf y logo_final.png"
    )
    conv_id = import_one(text)
    run_extraction(conv_id)

    graph = build_graph()
    cid = node_id("conversation", conv_id)
    contains_edges = [e for e in graph.edges if e.source == cid]
    target_types = {graph.get_node(e.target).type for e in contains_edges}
    assert target_types == {"project", "person", "task", "decision", "idea", "document", "asset"}
    for e in contains_edges:
        assert e.type == "contains"


def test_build_graph_confidence_present_on_object_nodes():
    conv_id = import_one("Decidimos usar Claude para el pipeline. Aprobado por todos.")
    run_extraction(conv_id)
    graph = build_graph()
    decision_nodes = [n for n in graph.nodes if n.type == "decision" and n.data.get("conversation_id") == conv_id]
    assert len(decision_nodes) == 1
    assert 0 < decision_nodes[0].data["confidence"] <= 1


def test_build_graph_no_duplicate_edges_across_rebuild():
    conv_id = import_one("Decidimos usar Claude para el pipeline. Aprobado por todos.")
    run_extraction(conv_id)
    run_extraction(conv_id)  # re-run: dedup happens in extraction, not here
    graph = build_graph()
    cid = node_id("conversation", conv_id)
    edges = [e for e in graph.edges if e.source == cid]
    # one decision object persisted (extraction dedup) => exactly one edge
    assert len(edges) == 1


# ---------------------------------------------------------------------------
# Empty / partial / orphaned data
# ---------------------------------------------------------------------------


def test_build_graph_handles_conversation_with_no_extraction():
    conv_id = import_one("this conversation was never extracted")
    graph = build_graph()
    cid = node_id("conversation", conv_id)
    assert graph.has_node(cid)
    assert [e for e in graph.edges if e.source == cid] == []


def test_build_graph_orphaned_object_still_a_node_without_edge():
    conv_id = import_one("Decidimos usar Claude para el pipeline. Aprobado por todos.")
    run_extraction(conv_id)

    from app.imports import db as imports_db

    assert imports_db.delete_conversation(conv_id) is True

    graph = build_graph()
    cid = node_id("conversation", conv_id)
    assert not graph.has_node(cid)
    decision_nodes = [n for n in graph.nodes if n.type == "decision" and n.data.get("conversation_id") == conv_id]
    assert len(decision_nodes) == 1  # object still present
    assert [e for e in graph.edges if e.target == decision_nodes[0].id] == []  # but not linked


def test_build_graph_is_empty_for_fresh_databases(tmp_path):
    """No conversations, no extracted objects: the graph must come back
    empty, not raise."""
    from app.config import Settings

    settings = Settings()
    settings.imports_db_path = tmp_path / "role_os_imports.db"
    settings.extraction_db_path = tmp_path / "role_os_extraction.db"

    graph = build_graph(settings)
    assert graph.nodes == []
    assert graph.edges == []
