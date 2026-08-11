"""The one canonical recommendation shape every rule pack normalizes into.

Every recommendation this engine returns carries exactly these fields (the
sprint brief's own list) plus a small number of documented extras that make
the canonical shape a strict superset of what every existing consumer
(Mission Control, Advisor, Explorer) already expects:

Required by the brief:
    recommendation      -- str, the action being suggested (a short title)
    priority             -- int, 0-100 (already on this scale in both source
                             rule packs -- see `engine.py`'s "Priority
                             calculation" note; never renormalized here)
    confidence           -- float, 0.0-1.0
    evidence              -- list[str], the concrete facts backing the claim
    project               -- dict reference (item_id/canonical_project_id/
                             display_name), or `None` for a workspace-wide
                             recommendation (e.g. "Discovery scan is stale")
    expected_benefit      -- str, a deterministic, static-lookup sentence
                             (see `_EXPECTED_BENEFIT_BY_KEYWORD` below) --
                             never inferred or generated
    suggested_action      -- str, what to actually do about it

Extras (not required by the brief, kept for backward compatibility with
existing callers and for readability):
    reason                -- str, one-sentence "why" (evidence is the list
                             of facts; reason is the prose summary of them)
    action_link            -- str | None, an in-app navigation target
    source                -- str, which rule pack produced this
                             ("discovery" | "pi" | "operational_intelligence")
    rule_id                -- str, the specific rule that fired
"""

from __future__ import annotations

from typing import Any

# A static, deterministic keyword -> benefit-sentence lookup. This is the
# only place "expected_benefit" text comes from -- no rule computes its own
# free-text benefit, so adding a rule never means inventing new prose logic,
# and every benefit sentence is auditable in one place. Matched against the
# recommendation's `recommendation` title, case-insensitively, first match
# wins; `_DEFAULT_BENEFIT` is used when nothing matches.
_EXPECTED_BENEFIT_BY_KEYWORD: tuple[tuple[str, str], ...] = (
    ("commit or stash", "Prevents lost work and avoids future merge conflicts."),
    ("shipping", "Unlocks the commercial/launch value already sitting in this project."),
    ("continue", "Keeps momentum on work that's already in motion."),
    ("re-prioritize", "Surfaces a high-value project before it goes cold."),
    (
        "review for continued relevance",
        "Frees up attention currently spent tracking a dormant project.",
    ),
    ("readme", "Makes the project understandable to a future collaborator or future you."),
    ("roadmap", "Gives the project a visible plan instead of an implicit one."),
    ("tests", "Reduces the risk of a future change silently breaking something."),
    ("move risk", "Prevents a relocation from silently breaking hardcoded paths."),
    ("momentum", "Reinforces a productive streak while it's still active."),
    ("commercial path", "Turns already-produced assets into a decision instead of clutter."),
    ("blocker", "Removes the one thing standing between this project and its next milestone."),
    ("unblock", "Removes a cross-project dependency stall."),
    ("todo", "Clears small open work before it accumulates."),
    ("deliverable", "Moves a concrete, scoped output across the finish line."),
    ("decision", "Resolves an open question that's likely blocking other work."),
    ("reuse", "Avoids rebuilding a capability another project already has."),
    ("stale", "Keeps the portfolio's priorities based on current, not outdated, information."),
    ("scan", "Keeps every project's health/status signal accurate instead of out of date."),
    ("import", "Keeps imported conversation history current with recent work."),
    ("paused", "Confirms whether pending work on a paused project should resume or be closed out."),
)
_DEFAULT_BENEFIT = "Keeps the project's status and priorities accurate."


def expected_benefit_for(recommendation_title: str) -> str:
    title_lower = recommendation_title.lower()
    for keyword, benefit in _EXPECTED_BENEFIT_BY_KEYWORD:
        if keyword in title_lower:
            return benefit
    return _DEFAULT_BENEFIT


def project_ref(
    *,
    item_id: str | None = None,
    canonical_project_id: str | None = None,
    display_name: str | None = None,
) -> dict[str, Any] | None:
    if not item_id and not canonical_project_id:
        return None
    return {
        "item_id": item_id,
        "canonical_project_id": canonical_project_id,
        "display_name": display_name or item_id or canonical_project_id,
    }


def make_recommendation(
    *,
    recommendation: str,
    priority: int,
    confidence: float,
    evidence: list[str],
    project: dict[str, Any] | None,
    suggested_action: str,
    reason: str,
    action_link: str | None = None,
    source: str,
    rule_id: str,
    expected_benefit: str | None = None,
) -> dict[str, Any]:
    """The single place a canonical recommendation dict gets constructed --
    every rule pack's normalizer calls this instead of hand-building the
    dict, so the shape can never silently drift between rule packs."""
    return {
        "recommendation": recommendation,
        "priority": max(0, min(100, int(priority))),
        "confidence": round(max(0.0, min(1.0, float(confidence))), 2),
        "evidence": list(evidence),
        "project": project,
        "expected_benefit": expected_benefit or expected_benefit_for(recommendation),
        "suggested_action": suggested_action,
        "reason": reason,
        "action_link": action_link,
        "source": source,
        "rule_id": rule_id,
    }
