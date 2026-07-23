"""Missing-deliverables signal: ratio of delivered vs. planned deliverables."""

from __future__ import annotations

from typing import Any


def score_missing_deliverables(deliverables: list[dict[str, Any]]) -> int:
    """Score 0-100: higher means more tracked deliverables are "delivered".

    A project with no deliverables tracked yet gets a neutral-ish score
    rather than 0 or 100 — there's simply no signal either way.
    """
    total = len(deliverables)
    if total == 0:
        return 70
    delivered = sum(1 for d in deliverables if (d.get("status") or "planned") == "delivered")
    return round((delivered / total) * 100)
