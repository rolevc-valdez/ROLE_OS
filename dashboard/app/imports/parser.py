"""Parsing and normalization for ChatGPT conversation exports.

This module only reads and normalizes conversation metadata/content — title,
timestamps, participant roles, message text. It intentionally performs no
summarization, classification, tagging, or relationship inference; that is
the Builder's job (`builder/knowledge_extractor.py`), which this sprint does
not touch or reuse.

Supported input: the ChatGPT export's `conversations.json` shape — a JSON
array of conversation objects, each with `id`, `title`, `create_time`,
`update_time`, and a `mapping` of node-id -> {"message": {...}}. This is the
same shape already represented in `samples/chatgpt_export_example/`.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Iterator


class InvalidExportError(ValueError):
    """Raised when the export file itself cannot be read as a conversation list."""


def parse_export_bytes(raw: bytes) -> list[Any]:
    """Parse raw export bytes into a list of conversation records.

    Raises InvalidExportError for malformed JSON or a top-level shape that
    isn't a list of conversations — these are file-level failures, distinct
    from a single invalid conversation record within an otherwise-valid file.
    """
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InvalidExportError(f"File is not valid UTF-8 text: {exc}") from exc

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InvalidExportError(f"File is not valid JSON: {exc}") from exc

    if not isinstance(data, list):
        raise InvalidExportError("Expected a JSON array of conversations at the top level")

    return data


def _epoch_to_iso(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def _text_from_message(message: dict) -> str:
    content = (message or {}).get("content") or {}
    parts = content.get("parts") or []
    if not isinstance(parts, list):
        return ""
    return "\n".join(part for part in parts if isinstance(part, str)).strip()


def _ordered_messages(conversation: dict) -> list[tuple[float, str, str]]:
    mapping = conversation.get("mapping")
    if mapping is None:
        return []
    if not isinstance(mapping, dict):
        raise ValueError("malformed mapping: expected an object")

    messages: list[tuple[float, str, str]] = []
    for node in mapping.values():
        if not isinstance(node, dict):
            continue
        message = node.get("message")
        if not isinstance(message, dict):
            continue
        text = _text_from_message(message)
        if not text:
            continue
        role = ((message.get("author") or {}).get("role")) or "unknown"
        created = message.get("create_time") or 0
        try:
            created = float(created)
        except (TypeError, ValueError):
            created = 0.0
        messages.append((created, str(role), text))

    messages.sort(key=lambda item: item[0])
    return messages


def _content_hash(title: str, created_at: str | None, content: list[dict[str, Any]]) -> str:
    payload = json.dumps(
        {"title": title, "created_at": created_at, "content": content},
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def normalize_conversation(raw: Any, source: str = "chatgpt") -> dict[str, Any]:
    """Normalize a single raw conversation record.

    Returns a dict ready for persistence. Raises ValueError with a
    human-readable (content-free) reason if the record is invalid.
    """
    if not isinstance(raw, dict):
        raise ValueError("record is not a JSON object")

    external_id = raw.get("id")
    if external_id is not None and not isinstance(external_id, str):
        external_id = str(external_id)

    title = raw.get("title")
    title = title.strip() if isinstance(title, str) else ""

    try:
        ordered = _ordered_messages(raw)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    if not ordered and not title and not external_id:
        raise ValueError("no id, title, or extractable content")

    created_at = _epoch_to_iso(raw.get("create_time"))
    updated_at = _epoch_to_iso(raw.get("update_time"))

    content = [{"role": role, "text": text, "created_at": _epoch_to_iso(created)} for created, role, text in ordered]
    roles = sorted({role for _, role, _ in ordered})

    if external_id:
        fingerprint = f"id:{external_id}"
    else:
        fingerprint = "hash:" + _content_hash(title, created_at, content)

    return {
        "source": source,
        "external_id": external_id,
        "fingerprint": fingerprint,
        "title": title or "Untitled conversation",
        "created_at": created_at,
        "updated_at": updated_at,
        "message_count": len(content),
        "roles": roles,
        "content": content,
        "content_hash": _content_hash(title, updated_at or created_at, content),
    }


def iter_normalized(conversations: list[Any]) -> Iterator[tuple[int, dict[str, Any] | None, str | None]]:
    """Yield (index, record, error) for every conversation in the export.

    `record` is None and `error` is set when the record is invalid — the
    caller is expected to count it and continue, never raise.
    """
    for index, raw in enumerate(conversations):
        try:
            yield index, normalize_conversation(raw), None
        except ValueError as exc:
            yield index, None, str(exc)
