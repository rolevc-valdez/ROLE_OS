"""The one canonical relationship shape every detector produces, and the
enumeration of relationship types this engine understands.

No LLM, no embeddings, no vector database, no external AI API -- every
relationship traces back to a deterministic detector reading evidence
that already exists (PI dependencies/capabilities, the canonical Assets
index, Knowledge cards, git remotes, bounded documentation reads, and
workspace path structure). Nothing here guesses; a detector that finds no
evidence returns nothing rather than a low-confidence guess.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

# The complete set of relationship types this engine detects or derives.
# A given `Relationship.relationship_type` is always exactly one of these
# -- this tuple is the type enum, not a per-relationship field (a single
# relationship never "supports" more than one type at once; if a detector
# finds evidence for two different relationships between the same pair,
# e.g. both `depends_on` and `shares_assets`, that's two relationship
# records, not one record with two types).
SUPPORTED_TYPES: tuple[str, ...] = (
    "depends_on",
    "uses",
    "consumes",
    "produces",
    "extends",
    "shares_assets",
    "shares_prompts",
    "shares_documentation",
    "shares_knowledge",
    "shares_sessions",
    "blocks",
    "blocked_by",
    "related",
)

# `blocks`/`blocked_by` are always machine-derived from a `depends_on` edge
# plus the target's own *status* -- never their own detector, and never
# the target's *health tier* (a computed 0-100 score bucketed into
# healthy/warning/critical -- a fresh or thin project defaults to
# health_score=0, i.e. tier "critical", automatically, which would falsely
# flag nearly every brand-new project as "blocking" its dependents; a
# user/system-set `status` of "blocked"/"at_risk" is a deliberate signal,
# a computed health tier is not). Kept here so `graph.py` and
# `detectors.py` share one definition of "which statuses count as
# blocking."
BLOCKING_STATUSES = ("blocked", "at_risk")


def project_ref(
    *,
    canonical_project_id: str | None,
    item_id: str | None = None,
    display_name: str | None = None,
) -> dict[str, Any]:
    return {
        "canonical_project_id": canonical_project_id,
        "item_id": item_id,
        "display_name": display_name or canonical_project_id or item_id or "Unknown project",
    }


def _project_key(ref: dict[str, Any]) -> str:
    return ref.get("canonical_project_id") or ref.get("item_id") or ref.get("display_name") or ""


def relationship_id(
    source: dict[str, Any], target: dict[str, Any], relationship_type: str, detector: str
) -> str:
    """Deterministic, stable across recomputation (the same evidence always
    produces the same id) -- required so a manual override (dismiss/
    confirm) keyed by this id survives the relationship being recomputed
    fresh on every request."""
    raw = f"{_project_key(source)}|{_project_key(target)}|{relationship_type}|{detector}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def make_relationship(
    *,
    source_project: dict[str, Any],
    target_project: dict[str, Any],
    relationship_type: str,
    confidence: float,
    evidence: list[str],
    detector: str,
    status: str = "active",
    manual_override: bool = False,
    last_verified: str | None = None,
) -> dict[str, Any]:
    """The single place a canonical relationship dict gets constructed --
    every detector calls this instead of hand-building the dict."""
    assert (
        relationship_type in SUPPORTED_TYPES
    ), f"unsupported relationship_type: {relationship_type}"
    now = datetime.now(timezone.utc).isoformat()
    return {
        "relationship_id": relationship_id(
            source_project, target_project, relationship_type, detector
        ),
        "source_project": source_project,
        "target_project": target_project,
        "relationship_type": relationship_type,
        "confidence": round(max(0.0, min(1.0, float(confidence))), 2),
        "evidence": list(evidence),
        "detector": detector,
        "discovered_at": now,
        "last_verified": last_verified or now,
        "manual_override": manual_override,
        "status": status,
    }
