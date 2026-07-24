"""Import orchestration: parse -> normalize -> deduplicate -> persist -> report.

Kept separate from the API route and the CLI command so both can call the
same tested logic (`run_import`) instead of duplicating it.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from app.config import Settings, get_settings
from app.imports import db
from app.imports.parser import InvalidExportError, iter_normalized, parse_export_bytes


def _file_fingerprint(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_import(raw: bytes, filename: str, settings: Settings | None = None) -> dict[str, Any]:
    """Import a ChatGPT export from raw file bytes.

    Never raises for per-record problems (those are counted as "invalid").
    Raises `InvalidExportError` only for a file-level failure: unreadable
    JSON or a top-level shape that isn't a conversation list.
    """
    settings = settings or get_settings()
    started_at = _now_iso()
    source_fingerprint = _file_fingerprint(raw)
    run_id = db.new_id()

    conversations = parse_export_bytes(raw)  # may raise InvalidExportError

    imported = updated = skipped = invalid = 0
    errors: list[dict[str, Any]] = []

    with db.get_connection(settings) as conn:
        for index, record, error in iter_normalized(conversations):
            if error is not None:
                invalid += 1
                errors.append({"index": index, "reason": error})
                continue

            record["source_file"] = filename
            record["source_fingerprint"] = source_fingerprint
            record["status"] = "imported"
            record["import_run_id"] = run_id

            existing = db.get_by_fingerprint(record["fingerprint"], conn)
            if existing is None:
                db.insert_conversation(record, conn)
                imported += 1
            elif existing["content_hash"] != record["content_hash"]:
                db.update_conversation(existing["id"], record, conn)
                updated += 1
            else:
                db.touch_conversation(existing["id"], conn)
                skipped += 1

    summary = {
        "status": "completed",
        "source_filename": filename,
        "source_fingerprint": source_fingerprint,
        "total_found": len(conversations),
        "imported": imported,
        "updated": updated,
        "skipped": skipped,
        "invalid": invalid,
        "errors": errors,
        "started_at": started_at,
        "completed_at": _now_iso(),
    }
    return db.record_run(summary, settings, run_id=run_id)


__all__ = ["run_import", "InvalidExportError"]
