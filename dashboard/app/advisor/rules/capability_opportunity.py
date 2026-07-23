"""Flags a project that could reuse a capability already exposed by
another project instead of rebuilding it from scratch.

Matching is deliberately simple and deterministic (no embeddings/AI): a
capability's `category` matching one of the project's `tags`, or the
capability's `name` appearing as a keyword in the project's description.
Only the single strongest match is surfaced per project, since this rule
produces exactly one recommendation type per project (consistent with the
engine's one-row-per-project-per-type dedupe model).
"""

from __future__ import annotations

from app.advisor.models import RecommendationCandidate, RuleContext
from app.advisor.scoring import confidence_from_availability, priority_weight, weighted_combine

WEIGHTS = {"priority": 0.3, "match_strength": 0.7}


def _find_best_match(project: dict, context: RuleContext) -> tuple[dict, str, bool] | None:
    tags_lower = {t.lower() for t in (project.get("tags") or [])}
    description_lower = (project.get("description") or "").lower()
    consumed_ids = {c["id"] for c in context.capabilities_consumed}

    best = None
    for cap in context.all_capabilities:
        if cap.get("project_id") == project.get("id") or cap.get("id") in consumed_ids:
            continue
        category = (cap.get("category") or "").lower()
        name = (cap.get("name") or "").lower()

        if category and category in tags_lower:
            return cap, category, True  # tag match is the strongest signal; return immediately
        if name and name in description_lower and best is None:
            best = (cap, name, False)
    return best


def evaluate(project: dict, context: RuleContext) -> list[RecommendationCandidate]:
    match = _find_best_match(project, context)
    if not match:
        return []

    capability, matched_on, is_tag_match = match
    provider_name = capability.get("provider_project_name") or "another project"

    signals = {
        "priority": priority_weight(project.get("priority")),
        "match_strength": 90 if is_tag_match else 60,
    }
    priority_score = weighted_combine(signals, WEIGHTS)
    confidence = confidence_from_availability([is_tag_match, True])

    match_kind = f"tag '{matched_on}'" if is_tag_match else f"keyword '{matched_on}' in the description"
    evidence = [f"'{capability['name']}' from {provider_name} matches {match_kind}"]

    candidate = RecommendationCandidate(
        project_id=project["id"],
        workspace=project.get("workspace", ""),
        title=f"Reuse '{capability['name']}' instead of rebuilding it",
        summary=f"{provider_name} already exposes '{capability['name']}', which matches {project['name']}.",
        recommendation_type="reuse_capability",
        priority_score=priority_score,
        confidence_score=confidence,
        reason=f"{project['name']} shows a {match_kind} for a capability already provided by {provider_name}.",
        evidence=evidence,
        suggested_action=f"Consume '{capability['name']}' from {provider_name} instead of rebuilding it.",
        estimated_effort="small",
        impact="Avoids duplicated work and keeps the capability's source of truth in one place.",
        ttl_days=14,
    )
    return [candidate]
