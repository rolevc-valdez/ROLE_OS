"""The Operational Intelligence Engine (Sprint C6): one canonical function,
`generate_recommendations`, composing three rule packs into one already-
normalized recommendation list. Nothing downstream (Mission Control,
Advisor, Explorer) picks between engines anymore -- there is one call.

Rule packs (registry)
----------------------
1. **Discovery pack** -- `app.workspace.advisor.ALL_RULES`, run via its
   existing orchestrator `generate_recommendations(enriched_items)`. Reuse,
   not reimplementation: git status, health, README/roadmap/tests presence,
   next action, business value, move risk, momentum, asset/commercial-
   readiness signals, and snapshot blockers.
2. **PI pack** -- `app.advisor.rules.ALL_RULES`, run via the existing,
   already-persisted orchestrator `app.advisor.engine.get_recommendations`.
   Reuse, not reimplementation: dependencies, capabilities, TODOs,
   deliverables, decisions, staleness, near-completion. Calling the
   already-persisted engine (rather than re-running its 8 rule modules
   statelessly here) keeps Advisor's own dismiss/complete/TTL lifecycle
   intact -- that lifecycle is Advisor-specific persisted state, not
   something this stateless engine should reinterpret.
3. **New evidence pack** -- `rules.ALL_RULES` (this package): Knowledge
   freshness, Discovery scan freshness, workspace-status-with-pending-work,
   and (Sprint C8) unblocking-a-dependent-project -- evidence dimensions
   neither existing pack evaluates. The unblocking rule reads only the
   Project Ecosystem Engine's cheap dependency detector (plain SQL against
   PI's `dependencies` table, via `project_ecosystem.detectors.
   detect_dependencies`) -- never the full ecosystem (which also runs the
   Assets-index/Knowledge/documentation detectors, each a real filesystem
   or bulk-table scan) -- so this engine's own "no repeated scans" contract
   holds regardless of whether a caller also asked for the full Project
   Ecosystem view in the same request.

Every pack's native shape is normalized into the one canonical shape
(`models.make_recommendation`) before being combined -- see `_normalize_
discovery_rec`/`_normalize_pi_rec` below for the exact field mapping.

Conflict resolution
--------------------
Two rules (from any pack, including the same pack) can legitimately fire
for the same project with overlapping advice -- e.g. the discovery pack's
"Keep the momentum going" and the PI pack's "Continue this project" both
firing because the same project has an open next action. Rather than
showing near-duplicate advice, recommendations are deduplicated by
`(project_key, recommendation.lower())` -- an identical title for the same
project (or workspace-wide, if `project` is None) collapses to whichever
instance has the higher `priority`, then higher `confidence`. Two
*different* recommendations for the same project are never collapsed --
only literal title collisions are.

Priority calculation
----------------------
No new scoring formula. Every rule pack already returns a 0-100 integer
priority on the same scale (discovery pack: hand-tuned per rule, documented
in `workspace/advisor.py`; PI pack: `app.advisor.scoring.weighted_combine`,
documented in `app/advisor/scoring.py`; new pack: a fixed priority per rule,
documented inline in `rules.py`) -- this engine only sorts by the value
each rule already assigned, it never recomputes or renormalizes priority.

Performance
------------
One call each to `all_project_contexts` (already the canonical "every
tracked project" list, computed once), `workspace_advisor.generate_
recommendations` (pure, no I/O beyond what's already in `enriched_items`),
`advisor_engine.get_recommendations` (one unfiltered call for the whole
workspace, not one call per project -- `refresh_recommendations` already
recomputes every project's health/rules internally regardless of any
`project_id` filter, so filtering per-project here would multiply that
work for no benefit), `workspace.service.get_freshness`, and `evidence.
knowledge_freshness`. No filesystem asset walk happens in this module at
all -- `all_project_contexts`'s caller is expected to run inside
`app.assets.service.request_scope()` if it also needs asset data in the
same request (see `mission_control/service.py`).
"""

from __future__ import annotations

from typing import Any

from app.advisor import engine as advisor_engine
from app.config import Settings, get_settings
from app.operational_intelligence import evidence as evidence_module
from app.operational_intelligence.models import make_recommendation, project_ref
from app.operational_intelligence.rules import ALL_RULES as NEW_RULES
from app.project_context.builder import all_project_contexts
from app.workspace import advisor as workspace_advisor
from app.workspace import service as workspace_service


def _normalize_discovery_rec(rec: dict[str, Any]) -> dict[str, Any]:
    return make_recommendation(
        recommendation=rec["recommendation"],
        priority=rec["priority"],
        confidence=rec["confidence"],
        evidence=rec.get("evidence") or [],
        project=project_ref(
            item_id=rec.get("item_id"),
            canonical_project_id=rec.get("canonical_project_id"),
            display_name=rec.get("project"),
        ),
        suggested_action=rec["recommendation"],
        reason=rec.get("reason", ""),
        action_link=rec.get("action_link"),
        source="discovery",
        rule_id="workspace_advisor",
    )


def _normalize_pi_rec(
    rec: dict[str, Any], contexts_by_canonical_id: dict[str, dict]
) -> dict[str, Any]:
    confidence_score = rec.get("confidence_score") or 0
    confidence = (
        float(confidence_score) / 100.0 if confidence_score > 1 else float(confidence_score)
    )
    context = contexts_by_canonical_id.get(rec.get("project_id"))
    return make_recommendation(
        recommendation=rec.get("title") or rec.get("suggested_action") or "Recommendation",
        priority=rec.get("priority_score", 0),
        confidence=confidence,
        evidence=rec.get("evidence") or [],
        project=project_ref(
            item_id=context.get("item_id") if context else None,
            canonical_project_id=rec.get("project_id"),
            display_name=(context.get("display_name") if context else None) or rec.get("workspace"),
        ),
        suggested_action=rec.get("suggested_action") or "",
        reason=rec.get("reason", ""),
        action_link=(f"#/project/{rec['project_id']}" if rec.get("project_id") else None),
        source="pi",
        rule_id=rec.get("recommendation_type", "app.advisor"),
    )


def _dedupe(recs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """See module docstring's "Conflict resolution" section."""
    best_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for rec in recs:
        project = rec.get("project")
        project_key = (
            (project["canonical_project_id"] or project["item_id"]) if project else "workspace"
        )
        key = (project_key, rec["recommendation"].strip().lower())
        existing = best_by_key.get(key)
        if existing is None or (rec["priority"], rec["confidence"]) > (
            existing["priority"],
            existing["confidence"],
        ):
            best_by_key[key] = rec
    return list(best_by_key.values())


def generate_recommendations(
    settings: Settings | None = None,
    *,
    all_contexts: list[dict[str, Any]] | None = None,
    enriched_items: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """The one canonical entry point -- see module docstring.

    `all_contexts`/`enriched_items` let a caller that already computed
    `all_project_contexts()` for the same request (e.g. Mission Control)
    pass it straight through, instead of this function silently
    recomputing "every tracked project" a second time -- both must be
    provided together or neither."""
    settings = settings or get_settings()

    if all_contexts is None or enriched_items is None:
        all_contexts, enriched_items = all_project_contexts(settings=settings)
    contexts_by_canonical_id = {c["id"]: c for c in all_contexts}

    recs: list[dict[str, Any]] = []

    for rec in workspace_advisor.generate_recommendations(enriched_items):
        recs.append(_normalize_discovery_rec(rec))

    for rec in advisor_engine.get_recommendations(settings=settings):
        recs.append(_normalize_pi_rec(rec, contexts_by_canonical_id))

    from app.project_ecosystem.detectors import detect_dependencies

    bundle = {
        "all_contexts": all_contexts,
        "enriched_items": enriched_items,
        "discovery_freshness": workspace_service.get_freshness(settings=settings),
        "knowledge_freshness": evidence_module.knowledge_freshness(settings=settings),
        # Sprint C8: cheap dependency-only ecosystem evidence (plain SQL,
        # no filesystem/knowledge scan) -- see module docstring point 3.
        "ecosystem_dependencies": detect_dependencies(all_contexts, settings),
        "settings": settings,
    }
    for rule in NEW_RULES:
        recs.extend(rule(bundle))

    recs = _dedupe(recs)
    recs.sort(key=lambda r: (r["priority"], r["confidence"]), reverse=True)
    return recs
