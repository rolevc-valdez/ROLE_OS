"""Modular Health Score engine (Epic 1).

Each signal is an independent, pure function scoring one dimension of
project health from 0 (bad) to 100 (great). `compute_health_score()`
combines whichever signals are available into one 0-100 score using
weights, renormalizing when a signal is unavailable (e.g. no commit data
source configured yet) so the algorithm degrades gracefully rather than
penalizing projects for missing, optional data.

Adding a new signal means: write a new pure function in its own module,
import it here, add it to `SIGNAL_WEIGHTS`, and pass its inputs through
`compute_health_score()`. Nothing else needs to change.
"""

from __future__ import annotations

from typing import Any

from .activity import score_recent_activity
from .commits import score_recent_commits
from .conversations import score_recent_conversations
from .decisions import score_unresolved_decisions
from .deliverables import score_missing_deliverables
from .todos import score_open_todos

__all__ = ["compute_health_score", "SIGNAL_WEIGHTS"]

# Relative importance of each signal. Only signals that produced a value are
# used — weights are renormalized over the signals actually present.
SIGNAL_WEIGHTS: dict[str, float] = {
    "recent_activity": 0.25,
    "open_todos": 0.20,
    "unresolved_decisions": 0.15,
    "missing_deliverables": 0.15,
    "recent_conversations": 0.15,
    "recent_commits": 0.10,
}


def compute_health_score(
    project: dict[str, Any],
    *,
    conversation_dates: list[str] | None = None,
    commit_dates: list[str] | None = None,
) -> dict[str, Any]:
    """Compute a project's Health Score (0-100) and its per-signal breakdown.

    Args:
        project: A project dict with at least `updated_at`, `todos`,
            `decisions`, and `deliverables`.
        conversation_dates: ISO dates of conversations linked to the
            project (from the knowledge base), used for the
            "recent_conversations" signal.
        commit_dates: ISO dates of recent commits, if a git integration is
            available. `None` (the default) means "no data source" and the
            "recent_commits" signal is excluded from scoring rather than
            counted against the project.
    """
    signals: dict[str, int] = {
        "recent_activity": score_recent_activity(project.get("updated_at")),
        "open_todos": score_open_todos(project.get("todos") or []),
        "unresolved_decisions": score_unresolved_decisions(project.get("decisions") or []),
        "missing_deliverables": score_missing_deliverables(project.get("deliverables") or []),
        "recent_conversations": score_recent_conversations(conversation_dates or []),
    }

    commits_score = score_recent_commits(commit_dates)
    if commits_score is not None:
        signals["recent_commits"] = commits_score

    active_weights = {k: SIGNAL_WEIGHTS[k] for k in signals}
    total_weight = sum(active_weights.values()) or 1.0
    weighted_sum = sum(signals[k] * active_weights[k] for k in signals)
    score = round(max(0.0, min(100.0, weighted_sum / total_weight)))

    return {"score": score, "breakdown": signals}
