"""Canonical health-tier bucketing (Sprint C1B: Rewiring).

Sprint C1's `builder.py` and the frontend (`app.js`) independently invented
disagreeing thresholds for the same three tiers (80/50 in the builder,
70/40 in the UI) -- a project scoring 75 was "healthy" in the API and
"warning" everywhere it was actually rendered. This module is now the one
place the numeric cutoffs exist; `builder.py` imports it, and the frontend
must render whatever tier the backend returns instead of recomputing one
(see `healthTier` in `app.js`, which now only exists as a legacy fallback
for the few payloads that don't yet carry a computed tier, and is kept in
sync with these exact numbers -- if you change them here, change it there
too, or better, finish wiring that payload through `ProjectContext`).

This does not unify *how* the underlying `health_score` number is computed
-- `app.discovery.health.compute_health()` (8 signals, for discovered
folders) and `app.projects.health.compute_health_score()` (6 signals, for
manually-created Project Intelligence projects) remain two distinct,
differently-weighted algorithms answering two different questions ("is
this discovered folder in good shape" vs "is this manually-tracked
project's PI data healthy"). `ProjectContext.health_score_source` names
which one produced a given project's score so a consumer never has to
guess which algorithm is behind the number.
"""

from __future__ import annotations

HEALTHY_THRESHOLD = 80
WARNING_THRESHOLD = 50


def health_tier(health_score: float | None) -> str | None:
    """The single, shared bucketing of a numeric health score into
    "healthy" / "warning" / "critical" / `None`."""
    if health_score is None:
        return None
    if health_score >= HEALTHY_THRESHOLD:
        return "healthy"
    if health_score >= WARNING_THRESHOLD:
        return "warning"
    return "critical"
