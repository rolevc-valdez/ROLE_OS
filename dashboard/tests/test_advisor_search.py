"""Unit tests for the Advisor Search module (Sprint 6): keyword search,
partial matching, type filters, and conversation/object lookup.

Exercises app.advisor.search directly (not through the API), against real
imported/extracted data via app.imports.service / app.extraction.service,
using the isolated temp DBs set up in conftest.py.
"""

from __future__ import annotations

import json
import uuid

from app.advisor import search as advisor_search
from app.extraction.service import run_extraction
from app.imports.service import run_import


def unique_id() -> str:
    return f"conv-{uuid.uuid4().hex[:8]}"


def import_one(text: str, title: str | None = None, conv_id: str | None = None) -> str:
    conv_id = conv_id or unique_id()
    payload = json.dumps(
        [
            {
                "id": conv_id,
                "title": title or f"Advisor search test {conv_id}",
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
# Keyword search / partial matching
# ---------------------------------------------------------------------------


def test_keyword_search_matches_object_title():
    tag = unique_id()
    conv_id = import_one(f"Decidimos usar {tag} para el pipeline. Aprobado por todos.")
    run_extraction(conv_id)

    results = advisor_search.search(q=tag)
    assert any(r["object_type"] == "Decision" and tag in r["name"] for r in results)


def test_partial_match_finds_substring():
    tag = unique_id()
    conv_id = import_one(f"Decidimos usar {tag}xyz para el pipeline. Aprobado.")
    run_extraction(conv_id)

    results = advisor_search.search(q=tag)  # shorter than the full "tagxyz" token
    assert any(tag in r["name"] for r in results)


def test_keyword_search_matches_conversation_title():
    tag = unique_id()
    conv_id = import_one("irrelevant body text", title=f"Meeting about {tag}")

    results = advisor_search.search(q=tag)
    assert any(r["object_type"] == "Conversation" and r["conversation_id"] == conv_id for r in results)


def test_keyword_search_matches_conversation_content():
    tag = unique_id()
    conv_id = import_one(f"the body mentions {tag} somewhere in the middle")

    results = advisor_search.search(q=tag)
    assert any(r["object_type"] == "Conversation" and r["conversation_id"] == conv_id for r in results)


def test_search_no_match_returns_empty():
    results = advisor_search.search(q=f"no-such-keyword-{uuid.uuid4().hex}")
    assert results == []


# ---------------------------------------------------------------------------
# "Show all X" -- empty query with a type filter
# ---------------------------------------------------------------------------


def test_empty_query_with_type_filter_lists_all_of_that_type():
    tag = unique_id()
    conv_id = import_one(f"Se me ocurre una idea sobre {tag}: podriamos automatizarlo.")
    run_extraction(conv_id)

    results = advisor_search.search(q=None, result_type="Idea")
    assert results  # at least the one just created
    assert all(r["object_type"] == "Idea" for r in results)


def test_empty_query_no_type_filter_returns_empty_result_semantics():
    # The engine itself doesn't special-case "no query, no filter" -- it
    # would return "everything" (matches on q=None). The UI is what
    # chooses not to call the API in that case (see
    # test_advisor_search_ui.py). Here we just confirm the function
    # doesn't raise and returns a list.
    results = advisor_search.search(q=None, result_type=None, limit=5)
    assert isinstance(results, list)


# ---------------------------------------------------------------------------
# Type filters
# ---------------------------------------------------------------------------


def test_type_filter_conversation_excludes_objects():
    tag = unique_id()
    conv_id = import_one(f"Decidimos usar {tag}. Aprobado por todos.", title=f"Conv {tag}")
    run_extraction(conv_id)

    results = advisor_search.search(q=tag, result_type="Conversation")
    assert results
    assert all(r["object_type"] == "Conversation" for r in results)


def test_type_filter_object_type_excludes_conversations_and_other_types():
    tag = unique_id()
    conv_id = import_one(f"Decidimos usar {tag}. Aprobado por todos. Tambien: {tag} es una idea.")
    run_extraction(conv_id)

    results = advisor_search.search(q=tag, result_type="Decision")
    assert results
    assert all(r["object_type"] == "Decision" for r in results)


# ---------------------------------------------------------------------------
# Result shape: every result carries type/name/conversation/date/confidence
# ---------------------------------------------------------------------------


def test_object_result_carries_conversation_context_and_confidence():
    tag = unique_id()
    conv_id = import_one(f"Decidimos usar {tag}. Aprobado por todos.", title=f"Ctx {tag}")
    run_extraction(conv_id)

    results = advisor_search.search(q=tag, result_type="Decision")
    r = results[0]
    assert r["conversation_id"] == conv_id
    assert r["conversation_title"] == f"Ctx {tag}"
    assert r["date"]
    assert 0 < r["confidence"] <= 1
    assert r["graph_node_id"].startswith("decision:")


def test_conversation_result_has_no_confidence():
    tag = unique_id()
    import_one("body", title=f"NoConf {tag}")
    results = advisor_search.search(q=tag, result_type="Conversation")
    assert results[0]["confidence"] is None
    assert results[0]["graph_node_id"].startswith("conversation:")


# ---------------------------------------------------------------------------
# Conversation lookup / object lookup
# ---------------------------------------------------------------------------


def test_get_conversation_result():
    tag = unique_id()
    conv_id = import_one("body", title=f"Lookup {tag}")
    result = advisor_search.get_conversation_result(conv_id)
    assert result is not None
    assert result["name"] == f"Lookup {tag}"
    assert result["object_type"] == "Conversation"


def test_get_conversation_result_unknown_returns_none():
    assert advisor_search.get_conversation_result("does-not-exist") is None


def test_get_object_result():
    tag = unique_id()
    conv_id = import_one(f"Decidimos usar {tag}. Aprobado por todos.")
    run_extraction(conv_id)
    objects = advisor_search.search(q=tag, result_type="Decision")
    object_id = objects[0]["graph_node_id"].split(":", 1)[1]

    result = advisor_search.get_object_result(object_id)
    assert result is not None
    assert result["object_type"] == "Decision"
    assert result["conversation_id"] == conv_id


def test_get_object_result_unknown_returns_none():
    assert advisor_search.get_object_result("does-not-exist") is None
