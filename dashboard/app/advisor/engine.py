"""The Advisor orchestrator: runs every rule against every project, merges
and deduplicates the results, persists them, and assembles the Daily
Brief.

Design summary
--------------
1. `refresh_recommendations()` loads all Projects (Project Intelligence,
   Epic 1) plus their Health Scores, dependencies/dependents, and
   capabilities, builds one `RuleContext` per project, and runs all eight
   rules (`app.advisor.rules.ALL_RULES`) against each one.
2. Candidates that share a dedupe key (`project_id:recommendation_type`)
   — whether from the same rule or two different rules — are merged,
   keeping only the highest-`priority_score` one, *before* touching the
   database. This is what keeps "avoid duplicate active recommendations"
   true even within a single generation pass, not just across runs.
3. For each surviving candidate, the engine asks the database whether a
   still-live row already exists for that key; if so it's left alone
   (dismissed/completed state is never overwritten), otherwise a new row
   is inserted.
4. Everything downstream (`get_recommendations`, `get_daily_brief`) reads
   from the database via `app.advisor.db.list_recommendations`, which is
   where the actual dismissed/completed/priority filtering happens.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app import db as knowledge_db
from app.advisor import db as advisor_db
from app.advisor.models import RecommendationCandidate, RuleContext
from app.advisor.narrative import AdvisorNarrativeProvider, get_default_narrative_provider
from app.advisor.rules import ALL_RULES
from app.config import Settings, get_settings
from app.projects import db as projects_db
from app.projects.health import compute_health_score

RISK_TYPES = {"review_risk", "review_decision"}
NEAR_COMPLETION_TYPES = {"continue_project", "finish_deliverable"}


def _conversation_dates_for_project(project: dict, settings: Settings) -> list[str]:
    dates: list[str] = []
    for conversation_id in project.get("conversations", []):
        try:
            card = knowledge_db.get_card(conversation_id, settings)
        except knowledge_db.DatabaseUnavailableError:
            break
        if card and card.get("updated"):
            dates.append(card["updated"])
    return dates


def _enrich_capabilities_with_provider_name(
    capabilities: list[dict], projects_by_id: dict[str, dict]
) -> list[dict]:
    enriched = []
    for cap in capabilities:
        cap = dict(cap)
        provider = projects_by_id.get(cap.get("project_id"))
        cap["provider_project_name"] = provider["name"] if provider else "another project"
        enriched.append(cap)
    return enriched


def _enrich_dependencies_with_health(
    dependencies: list[dict], projects_by_id: dict[str, dict]
) -> list[dict]:
    enriched = []
    for dep in dependencies:
        dep = dict(dep)
        target = projects_by_id.get(dep.get("depends_on_project_id"))
        dep["depends_on_health_score"] = target.get("health_score") if target else None
        dep["depends_on_status"] = target.get("status") if target else None
        enriched.append(dep)
    return enriched


def _build_context(
    project: dict,
    *,
    projects_by_id: dict[str, dict],
    all_capabilities: list[dict],
    settings: Settings,
    now: datetime,
) -> RuleContext:
    dependencies = _enrich_dependencies_with_health(
        projects_db.list_dependencies(project["id"], settings), projects_by_id
    )
    dependents = projects_db.list_dependents(project["id"], settings)
    capabilities_provided = [c for c in all_capabilities if c["project_id"] == project["id"]]
    capabilities_consumed = projects_db.list_consumed_capabilities(project["id"], settings)
    conversation_dates = _conversation_dates_for_project(project, settings)
    # Reuse the health score computed in the up-front refresh pass (see
    # refresh_recommendations) instead of recomputing it a second time.
    health = project.get("_health") or compute_health_score(project, conversation_dates=conversation_dates)

    return RuleContext(
        dependencies=dependencies,
        dependents=dependents,
        capabilities_provided=capabilities_provided,
        capabilities_consumed=capabilities_consumed,
        all_capabilities=all_capabilities,
        conversation_dates=conversation_dates,
        health=health,
        now=now,
    )


def refresh_recommendations(
    *, workspace: str | None = None, settings: Settings | None = None
) -> list[dict[str, Any]]:
    """Run every rule against every relevant project and persist new findings.

    Returns the up-to-date (persisted-or-already-live) recommendation rows
    for the projects considered in this pass, but callers that want a
    filtered/sorted view should query `app.advisor.db.list_recommendations`
    afterwards instead of relying on this return value directly.
    """
    settings = settings or get_settings()
    now = datetime.now(timezone.utc)

    all_projects = projects_db.list_projects(settings=settings)

    # Refresh every project's Health Score up front (not just the ones in
    # the target workspace) so cross-project checks like blocked_dependency
    # always compare against current data, never a stale/default stored
    # value from before anyone last opened that project's health endpoint.
    for project in all_projects:
        conversation_dates = _conversation_dates_for_project(project, settings)
        health = compute_health_score(project, conversation_dates=conversation_dates)
        projects_db.set_health_score(project["id"], health["score"], settings)
        project["health_score"] = health["score"]
        project["_health"] = health  # cache so target projects don't recompute

    projects_by_id = {p["id"]: p for p in all_projects}
    all_capabilities = _enrich_capabilities_with_provider_name(
        projects_db.list_capabilities(settings=settings), projects_by_id
    )

    target_projects = [p for p in all_projects if not workspace or p["workspace"] == workspace]

    all_candidates: list[RecommendationCandidate] = []
    for project in target_projects:
        context = _build_context(
            project, projects_by_id=projects_by_id, all_capabilities=all_capabilities, settings=settings, now=now
        )
        for rule in ALL_RULES:
            all_candidates.extend(rule.evaluate(project, context))

    # Merge same-key candidates (possibly from different rules) within this
    # pass, keeping only the highest-priority one, before touching the DB.
    best_by_key: dict[str, RecommendationCandidate] = {}
    for candidate in all_candidates:
        key = candidate.dedupe_key()
        if key not in best_by_key or candidate.priority_score > best_by_key[key].priority_score:
            best_by_key[key] = candidate

    persisted: list[dict[str, Any]] = []
    for key, candidate in best_by_key.items():
        existing = advisor_db.find_live_by_dedupe_key(key, settings)
        persisted.append(existing if existing else advisor_db.insert_recommendation(candidate, settings))

    return persisted


def get_recommendations(
    *,
    workspace: str | None = None,
    project_id: str | None = None,
    recommendation_type: str | None = None,
    minimum_priority_score: int | None = None,
    include_dismissed: bool = False,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    settings = settings or get_settings()
    refresh_recommendations(workspace=workspace, settings=settings)
    return advisor_db.list_recommendations(
        workspace=workspace,
        project_id=project_id,
        recommendation_type=recommendation_type,
        minimum_priority_score=minimum_priority_score,
        include_dismissed=include_dismissed,
        settings=settings,
    )


def get_recommendation(recommendation_id: str, settings: Settings | None = None) -> dict[str, Any] | None:
    return advisor_db.get_recommendation(recommendation_id, settings or get_settings())


def dismiss_recommendation(recommendation_id: str, settings: Settings | None = None) -> dict[str, Any] | None:
    return advisor_db.dismiss_recommendation(recommendation_id, settings or get_settings())


def complete_recommendation(recommendation_id: str, settings: Settings | None = None) -> dict[str, Any] | None:
    return advisor_db.complete_recommendation(recommendation_id, settings or get_settings())


def _project_display_name(project_id: str, projects_by_id: dict[str, dict]) -> str:
    project = projects_by_id.get(project_id)
    return project["name"] if project else project_id


def generate_daily_brief(
    *,
    workspace: str | None = None,
    greeting_name: str = "Role",
    settings: Settings | None = None,
    narrative: AdvisorNarrativeProvider | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    narrative = narrative or get_default_narrative_provider()

    refresh_recommendations(workspace=workspace, settings=settings)
    live_recs = advisor_db.list_recommendations(
        workspace=workspace, include_dismissed=False, include_completed=False, settings=settings
    )

    projects_by_id = {p["id"]: p for p in projects_db.list_projects(settings=settings)}

    def to_item(rec: dict) -> dict:
        return {
            "project_id": rec["project_id"],
            "project_name": _project_display_name(rec["project_id"], projects_by_id),
            "headline": f"{_project_display_name(rec['project_id'], projects_by_id)} — {rec['suggested_action']}",
            "explanation": rec["impact"] or rec["reason"],
            "recommendation_id": rec["id"],
        }

    top_recommended = [to_item(r) for r in live_recs[:3]]
    critical_risks = [to_item(r) for r in live_recs if r["recommendation_type"] in RISK_TYPES]
    blocked = [to_item(r) for r in live_recs if r["recommendation_type"] == "unblock_dependency"]
    near_completion = [to_item(r) for r in live_recs if r["recommendation_type"] in NEAR_COMPLETION_TYPES]
    stale_high_priority = [
        to_item(r)
        for r in live_recs
        if r["recommendation_type"] in {"update_stale_project", "review_risk"}
        and (projects_by_id.get(r["project_id"], {}).get("priority") in ("high", "critical"))
    ]
    capability_opportunities = [to_item(r) for r in live_recs if r["recommendation_type"] == "reuse_capability"]

    greeting = narrative.generate_daily_brief(
        greeting_name, {"top_recommended_projects": [item["headline"] for item in top_recommended]}
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "greeting": greeting,
        "top_recommended_projects": top_recommended,
        "critical_risks": critical_risks,
        "blocked_projects": blocked,
        "near_completion": near_completion,
        "stale_high_priority": stale_high_priority,
        "capability_opportunities": capability_opportunities,
    }
