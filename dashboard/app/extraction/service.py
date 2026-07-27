"""Extraction orchestration: read a conversation -> run rule-based
extractors -> deduplicate -> persist -> report.

Kept separate from the API route so it stays independently testable, same
split as `app/imports/service.py`.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from app.config import Settings, get_settings
from app.extraction import db, rules
from app.imports import db as imports_db


class ConversationNotFoundError(ValueError):
    """Raised when extraction is requested for an unknown conversation id."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_extraction(conversation_id: str, settings: Settings | None = None) -> dict[str, Any]:
    """Extract knowledge objects from one imported conversation.

    Idempotent / safe to re-run: each candidate is deduplicated within a
    conversation by a fingerprint of (conversation_id, object_type, title).
    A re-run never creates a duplicate row -- it inserts new objects,
    refreshes `updated_at`/confidence on ones that changed, and touches
    `updated_at` on ones that are identical to what's already stored.
    Objects from a previous run that no longer match are left alone (not
    auto-deleted); deletion is only ever explicit, via `delete_object`.
    """
    settings = settings or get_settings()
    conversation = imports_db.get_conversation(conversation_id, settings=settings)
    if conversation is None:
        raise ConversationNotFoundError(f"Conversation '{conversation_id}' not found")

    started_at = _now_iso()
    run_id = db.new_id()
    extracted = rules.extract_all(conversation["content"])

    created = updated = unchanged = 0
    counts_by_type: dict[str, int] = defaultdict(int)

    with db.get_connection(settings) as conn:
        for object_type, candidates in extracted.items():
            for title, confidence in candidates:
                counts_by_type[object_type] += 1
                fingerprint = db.make_fingerprint(conversation_id, object_type, title)
                record = {
                    "conversation_id": conversation_id,
                    "object_type": object_type,
                    "title": title,
                    "source": conversation["source"],
                    "confidence": confidence,
                    "fingerprint": fingerprint,
                    "extraction_run_id": run_id,
                }
                existing = db.get_by_fingerprint(fingerprint, conn)
                if existing is None:
                    db.insert_object(record, conn)
                    created += 1
                elif existing["confidence"] != confidence:
                    db.update_object(existing["id"], record, conn)
                    updated += 1
                else:
                    db.touch_object(existing["id"], conn)
                    unchanged += 1

    summary = {
        "conversation_id": conversation_id,
        "status": "completed",
        "total_found": sum(counts_by_type.values()),
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
        "counts_by_type": dict(counts_by_type),
        "started_at": started_at,
        "completed_at": _now_iso(),
    }
    return db.record_run(summary, settings, run_id=run_id)


__all__ = ["run_extraction", "ConversationNotFoundError"]
