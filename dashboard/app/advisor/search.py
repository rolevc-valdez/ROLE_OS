"""Advisor Search (Sprint 6): keyword/partial-match search over the
structured knowledge ROLE OS already has -- imported conversations and
their extracted knowledge objects. No AI, no LLM, no NLP, no embeddings,
no semantic search: every match is a plain, case-insensitive substring
match, same as the Conversation Explorer's own search and the Extraction
domain's `search_objects()` added alongside this file.

New, additive module inside the existing `app/advisor/` package -- the
Epic 2 recommendation engine (`db.py`, `engine.py`, `rules/`, `scoring.py`,
`narrative.py`) is untouched by this sprint.
"""

from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.extraction import db as extraction_db
from app.imports import db as imports_db


def _conversation_to_result(conversation: dict[str, Any]) -> dict[str, Any]:
    return {
        "object_type": "Conversation",
        "name": conversation["title"],
        "conversation_id": conversation["id"],
        "conversation_title": conversation["title"],
        "date": conversation.get("created_at"),
        "confidence": None,
        "graph_node_id": f"conversation:{conversation['id']}",
    }


def _object_to_result(obj: dict[str, Any], conversation_title: str | None) -> dict[str, Any]:
    return {
        "object_type": obj["object_type"],
        "name": obj["title"],
        "conversation_id": obj.get("conversation_id"),
        "conversation_title": conversation_title,
        "date": obj.get("created_at"),
        "confidence": obj.get("confidence"),
        "graph_node_id": f"{obj['object_type'].lower()}:{obj['id']}",
    }


def _conversation_title(conversation_id: str | None, settings: Settings) -> str | None:
    if not conversation_id:
        return None
    conversation = imports_db.get_conversation(conversation_id, settings=settings)
    return conversation["title"] if conversation else None


def search(
    q: str | None = None,
    result_type: str | None = None,
    limit: int = 100,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    """Search conversations and/or extracted objects by keyword, optionally
    narrowed to one result type. An empty/omitted `q` matches everything
    of the selected type(s) -- this is what makes "Show all projects"
    (result_type="Project", q=None) and "Show everything related to X"
    (result_type=None, q="X") both work through the same function.
    """
    settings = settings or get_settings()
    q = (q or "").strip() or None
    results: list[dict[str, Any]] = []

    include_conversations = result_type in (None, "Conversation")
    include_objects = result_type != "Conversation"

    if include_conversations:
        items, _total = imports_db.list_conversations_page(q=q, page=1, page_size=limit, settings=settings)
        results.extend(_conversation_to_result(c) for c in items)

    if include_objects:
        object_type = result_type if result_type not in (None, "Conversation") else None
        objects = extraction_db.search_objects(q=q, object_type=object_type, limit=limit, settings=settings)
        title_cache: dict[str, str | None] = {}
        for obj in objects:
            cid = obj.get("conversation_id")
            if cid not in title_cache:
                title_cache[cid] = _conversation_title(cid, settings)
            results.append(_object_to_result(obj, title_cache[cid]))

    results.sort(key=lambda r: r["date"] or "", reverse=True)
    return results[:limit]


def get_object_result(object_id: str, settings: Settings | None = None) -> dict[str, Any] | None:
    settings = settings or get_settings()
    obj = extraction_db.get_object(object_id, settings=settings)
    if obj is None:
        return None
    return _object_to_result(obj, _conversation_title(obj.get("conversation_id"), settings))


def get_conversation_result(conversation_id: str, settings: Settings | None = None) -> dict[str, Any] | None:
    settings = settings or get_settings()
    conversation = imports_db.get_conversation(conversation_id, settings=settings)
    if conversation is None:
        return None
    return _conversation_to_result(conversation)


__all__ = ["search", "get_object_result", "get_conversation_result"]
