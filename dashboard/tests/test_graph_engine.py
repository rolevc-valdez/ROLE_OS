"""Integration tests for `app.graph.engine.build_graph`, exercising the real
Project Intelligence DB layer plus a real knowledge SQLite file (built the
same way `builder.py` would), rather than hand-crafted dicts.
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from app.config import Settings
from app.graph.engine import build_graph
from app.projects import db as projects_db


def _write_knowledge_db(path, cards: list[dict]) -> None:
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE knowledge_cards(
          conversation_id TEXT PRIMARY KEY,
          title TEXT, project TEXT, category TEXT, status TEXT,
          date TEXT, updated TEXT, summary TEXT, card_json TEXT
        );
        """
    )
    conn.executemany(
        "INSERT INTO knowledge_cards VALUES(?,?,?,?,?,?,?,?,?)",
        [
            (
                c["conversation_id"], c["title"], c["project"], c.get("category", "GENERAL"),
                c.get("status", "Unknown"), c.get("date", ""), c.get("updated", ""),
                c.get("summary", ""), json.dumps(c),
            )
            for c in cards
        ],
    )
    conn.commit()
    conn.close()


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("ROLE_OS_PROJECTS_DB_PATH", str(tmp_path / "projects.db"))
    monkeypatch.setenv("ROLE_OS_ADVISOR_DB_PATH", str(tmp_path / "advisor.db"))
    monkeypatch.setenv("ROLE_OS_DB_PATH", str(tmp_path / "role_os.db"))
    return Settings()


def test_build_graph_degrades_gracefully_when_knowledge_db_missing(settings):
    projects_db.create_project(name="Solo Project", workspace="Ideas", settings=settings)
    graph = build_graph(settings)
    assert any(n.type == "Project" and n.label == "Solo Project" for n in graph.nodes)
    assert not any(n.type == "KnowledgeCard" for n in graph.nodes)


def test_build_graph_assembles_full_relationship_set(settings):
    p1 = projects_db.create_project(name="ROLE MASTER", workspace="Products", owner="Rogelio", settings=settings)
    p2 = projects_db.create_project(name="SUPER FACIL", workspace="Products", owner="Rogelio", settings=settings)
    projects_db.create_dependency(p2["id"], p1["id"], note="needs brand assets", settings=settings)
    cap = projects_db.create_capability(p1["id"], "Brand Identity", settings=settings)
    projects_db.consume_capability(cap["id"], p2["id"], settings=settings)
    projects_db.link_conversation(p1["id"], "conv-1", settings=settings)
    projects_db.add_collection_item(p1["id"], "decisions", {"text": "Use Claude"}, settings=settings)

    _write_knowledge_db(
        settings.db_path,
        [
            {
                "conversation_id": "conv-1",
                "title": "Master planning",
                "project": "ROLE_MASTER",
                "people": ["Ana Ruiz"],
                "applications": ["Claude"],
                "vendors": ["Anthropic"],
                "assets": ["brand.png"],
                "related_conversations": [],
            }
        ],
    )

    graph = build_graph(settings)
    edge_types_present = {e.type for e in graph.edges}
    expected = {
        "BELONGS_TO", "DEPENDS_ON", "UNBLOCKS", "IMPLEMENTS", "USES",
        "SHARES_CAPABILITY", "REFERENCES", "GENERATED_FROM", "MENTIONS", "PROVIDES",
    }
    assert expected <= edge_types_present

    node_types_present = {n.type for n in graph.nodes}
    expected_nodes = {
        "Project", "Workspace", "Capability", "Decision", "KnowledgeCard",
        "Conversation", "Person", "Application", "Vendor", "Asset",
    }
    assert expected_nodes <= node_types_present
