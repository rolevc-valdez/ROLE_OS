"""Risk scoring: fixed, documented thresholds over already-computed
relationship counts -- no hidden weighting, no magic numbers without a
comment explaining the choice. Every level is explainable by pointing at
the specific counts that produced it.
"""

from __future__ import annotations

from typing import Any

# A project already blocking 1+ others (Sprint C8's `blocks` relationship
# -- its own health/status is bad enough that a real dependent is stalled
# on it) is the single strongest "something is already wrong" signal this
# engine has -- always critical, regardless of dependent count.
_CRITICAL_IF_ALREADY_BLOCKING = 1

# Direct dependent counts at/above this are "critical" even without an
# active block -- enough live consumers that any change needs real
# coordination.
_CRITICAL_DIRECT_DEPENDENT_THRESHOLD = 5

# "high": several direct dependents, or a smaller number of direct
# dependents whose own dependents (transitive) add up meaningfully.
_HIGH_DIRECT_DEPENDENT_THRESHOLD = 3
_HIGH_TRANSITIVE_DEPENDENT_THRESHOLD = 3

# "medium": at least one real dependent, or any sharing relationship
# (assets/knowledge/docs/prompts/sessions) -- some real, if smaller,
# coordination cost.
_MEDIUM_DEPENDENT_THRESHOLD = 1
_MEDIUM_SHARE_THRESHOLD = 1


def compute_overall_risk(
    *,
    direct_dependents: list[dict[str, Any]],
    transitive_dependents: list[dict[str, Any]],
    blocks: list[dict[str, Any]],
    shared_counts: dict[str, int],
) -> tuple[str, list[str]]:
    """Returns `(risk_level, reasons)`. `reasons` names the exact counts
    that produced the level -- every level is explainable, never a bare
    label."""
    direct_count = len(direct_dependents)
    transitive_count = len(transitive_dependents)
    blocks_count = len(blocks)
    total_shares = sum(shared_counts.values())

    if blocks_count >= _CRITICAL_IF_ALREADY_BLOCKING:
        return "critical", [
            f"already blocking {blocks_count} project(s) due to this project's own health/status"
        ]
    if direct_count >= _CRITICAL_DIRECT_DEPENDENT_THRESHOLD:
        return "critical", [f"{direct_count} project(s) directly depend on this one"]

    if direct_count >= _HIGH_DIRECT_DEPENDENT_THRESHOLD:
        return "high", [f"{direct_count} project(s) directly depend on this one"]
    if (
        direct_count >= _MEDIUM_DEPENDENT_THRESHOLD
        and transitive_count >= _HIGH_TRANSITIVE_DEPENDENT_THRESHOLD
    ):
        return "high", [
            f"{direct_count} direct dependent(s), extending to {transitive_count} project(s) transitively"
        ]

    if direct_count >= _MEDIUM_DEPENDENT_THRESHOLD:
        return "medium", [f"{direct_count} project(s) directly depend on this one"]
    if total_shares >= _MEDIUM_SHARE_THRESHOLD:
        share_desc = ", ".join(f"{n} {k}" for k, n in shared_counts.items() if n)
        return "medium", [f"shares evidence with other projects: {share_desc}"]

    if transitive_count:
        return "low", [f"{transitive_count} project(s) affected only transitively"]

    return "none", ["no dependency, blocking, or sharing relationships detected"]


def average_confidence(relationships: list[dict[str, Any]]) -> float:
    if not relationships:
        return 0.0
    return round(sum(r["confidence"] for r in relationships) / len(relationships), 2)
