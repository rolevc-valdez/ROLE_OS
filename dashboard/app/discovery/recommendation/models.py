"""Data shape a recommendation rule returns. Mirrors the shape of
`app.advisor.models.RecommendationCandidate` (evaluate one condition,
return a candidate with the action, reasons, and a priority the engine
uses to pick a winner), scoped down to Discovery's simpler "exactly one of
six actions" problem instead of Advisor's "many simultaneous recommendation
types."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RecommendationCandidate:
    action: str
    reasons: list[str] = field(default_factory=list)
    # Higher wins. See `rules/__init__.py` for the full, documented
    # precedence table and why each rule has the priority it has.
    priority: int = 0
