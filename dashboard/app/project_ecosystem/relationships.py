"""Conflict resolution (dedupe) and manual-override application over a
raw list of detector output. Two different detectors can legitimately
find the same (source, target, type) pair with different evidence/
confidence (e.g. both a documentation text reference and a git remote
reference pointing at the same two projects as `related`) -- these merge
into one relationship carrying the union of evidence and the higher
confidence, never shown as duplicate cards.
"""

from __future__ import annotations

from typing import Any

from app.config import Settings
from app.project_ecosystem import db as ecosystem_db


def _dedupe_key(rel: dict[str, Any]) -> tuple[str, str, str]:
    def key(ref: dict[str, Any]) -> str:
        return (
            ref.get("canonical_project_id") or ref.get("item_id") or ref.get("display_name") or ""
        )

    return (key(rel["source_project"]), key(rel["target_project"]), rel["relationship_type"])


def dedupe(relationships: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[tuple[str, str, str], dict[str, Any]] = {}
    for rel in relationships:
        key = _dedupe_key(rel)
        existing = best.get(key)
        if existing is None:
            best[key] = dict(rel)
            continue
        merged_evidence = list(existing["evidence"])
        for item in rel["evidence"]:
            if item not in merged_evidence:
                merged_evidence.append(item)
        existing["evidence"] = merged_evidence
        if rel["confidence"] > existing["confidence"]:
            existing["confidence"] = rel["confidence"]
            existing["detector"] = f"{existing['detector']}+{rel['detector']}"
        elif rel["detector"] not in existing["detector"]:
            existing["detector"] = f"{existing['detector']}+{rel['detector']}"
    return list(best.values())


def apply_overrides(
    relationships: list[dict[str, Any]], settings: Settings | None = None
) -> list[dict[str, Any]]:
    """A dismissed relationship is excluded entirely (still recomputed
    every time -- the override just hides it, it never stops the detector
    from finding the same evidence again); a confirmed one is kept with
    `status="confirmed"`/`manual_override=True`."""
    overrides = ecosystem_db.list_overrides(settings=settings)
    if not overrides:
        return relationships
    result = []
    for rel in relationships:
        override_status = overrides.get(rel["relationship_id"])
        if override_status == "dismissed":
            continue
        if override_status == "confirmed":
            rel = dict(rel, status="confirmed", manual_override=True)
        result.append(rel)
    return result
