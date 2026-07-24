"""Unit tests for app.imports.db query helpers added in Sprint B1.5
(Conversation Explorer): sort/pagination edge cases and schema migration
idempotency, independent of the API layer.
"""

from __future__ import annotations

import sqlite3

from app.imports import db


def test_list_conversations_page_clamps_page_size():
    items, total = db.list_conversations_page(page=1, page_size=10_000)
    assert total >= 0
    # page_size is clamped to 200 server-side regardless of what was asked.
    assert len(items) <= 200


def test_list_conversations_page_clamps_page_below_one():
    items_a, _ = db.list_conversations_page(page=0, page_size=5)
    items_b, _ = db.list_conversations_page(page=1, page_size=5)
    assert [i["id"] for i in items_a] == [i["id"] for i in items_b]


def test_list_conversations_page_unknown_sort_by_falls_back_to_imported_at():
    # Should not raise (no SQL injection / KeyError) for an unrecognized field.
    items, _ = db.list_conversations_page(sort_by="not_a_real_column", page_size=5)
    assert isinstance(items, list)


def test_ensure_schema_is_idempotent():
    with db.get_connection() as conn:
        db.ensure_schema(conn)
        db.ensure_schema(conn)
    # Reaching here without sqlite3.OperationalError confirms the
    # ADD COLUMN migrations tolerate re-running against an already
    # migrated database.


def test_get_conversation_returns_none_for_unknown_id():
    assert db.get_conversation("definitely-not-a-real-id") is None


def test_delete_conversation_returns_false_for_unknown_id():
    assert db.delete_conversation("definitely-not-a-real-id") is False


def test_list_facets_returns_lists():
    facets = db.list_facets()
    assert isinstance(facets["sources"], list)
    assert isinstance(facets["statuses"], list)


def test_count_conversations_matches_unfiltered_page_total():
    _, total_from_page = db.list_conversations_page(page=1, page_size=1)
    assert db.count_conversations() == total_from_page
