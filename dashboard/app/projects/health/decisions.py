"""Unresolved-decisions signal: pending decisions drag health down."""

from __future__ import annotations

from typing import Any


def score_unresolved_decisions(decisions: list[dict[str, Any]]) -> int:
    """Score 0-100: higher means fewer decisions are still "pending"."""
    pending = sum(1 for d in decisions if (d.get("status") or "resolved") == "pending")
    if pending == 0:
        return 100
    if pending <= 1:
        return 75
    if pending <= 3:
        return 50
    return 20
