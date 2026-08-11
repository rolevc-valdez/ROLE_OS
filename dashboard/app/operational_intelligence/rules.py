"""New, deterministic rules covering the evidence dimensions the two
existing rule packs (`workspace.advisor.ALL_RULES` -- discovery/git/health
evidence, and `app.advisor.rules.ALL_RULES` -- dependencies/capabilities/
TODOs/deliverables/decisions evidence) do not evaluate today: Knowledge
freshness, Discovery scan freshness (already computed, never turned into
an actionable recommendation), and Workspace status combined with pending
work (a project's own overlay `status` crossed with whether it still has
open work -- neither existing engine reads `status` at all).

Every rule here has the same signature -- `rule(bundle: dict) -> list[dict]`
-- so `engine.py` runs the whole registry with one loop, never a growing
if/else chain. Each rule returns zero or more already-canonical
recommendation dicts (built via `models.make_recommendation`).
"""

from __future__ import annotations

from typing import Any

from app.operational_intelligence.models import make_recommendation, project_ref

# Mirrors `workspace.advisor`'s inactivity threshold in spirit (a project
# untouched for a while is worth flagging) but scoped to *paused/archived*
# status specifically -- a project a human explicitly paused isn't
# "inactive by neglect" (which `workspace.advisor.rule_inactive` already
# covers for anything still marked active), it's "paused with something
# left open," a genuinely different, previously-uncovered signal.
_PAUSED_STATUSES = ("paused", "on_hold", "archived")


def rule_discovery_scan_stale(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    freshness = bundle["discovery_freshness"]
    if not freshness.get("is_stale"):
        return []
    hours = freshness.get("hours_since_scan")
    age_text = f"{round(hours)}h since last scan" if hours is not None else "no scan on record"
    return [
        make_recommendation(
            recommendation="Rescan the Workspace",
            priority=50,
            confidence=1.0,
            evidence=[f"data_freshness.is_stale = true ({age_text})"],
            project=None,
            suggested_action="Rescan Workspace",
            reason="Discovery data is stale -- every project's health/git/next-action signal "
            "may be out of date until the next scan.",
            action_link="#/workspace",
            source="operational_intelligence",
            rule_id="rule_discovery_scan_stale",
        )
    ]


def rule_knowledge_stale(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    freshness = bundle["knowledge_freshness"]
    if not freshness.get("is_stale"):
        return []
    days = freshness.get("stale_threshold_days")
    last_import = freshness.get("last_import")
    age_text = f"last import: {last_import}" if last_import else "no import on record"
    return [
        make_recommendation(
            recommendation="Import recent conversations",
            priority=30,
            confidence=0.9,
            evidence=[f"knowledge_freshness.is_stale = true ({age_text}, threshold {days}d)"],
            project=None,
            suggested_action="Import ChatGPT conversations",
            reason="The Knowledge Graph has not seen a new imported conversation in over "
            f"{days} days -- it may no longer reflect recent decisions/work.",
            action_link="#/knowledge",
            source="operational_intelligence",
            rule_id="rule_knowledge_stale",
        )
    ]


def rule_paused_project_with_pending_work(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    recs = []
    for item in bundle["enriched_items"]:
        if not item.get("adopted"):
            continue
        status = (item.get("status") or "").lower()
        if status not in _PAUSED_STATUSES:
            continue
        next_action = item.get("next_action") or {}
        snapshot = (item.get("ai_sessions") or {}).get("latest_snapshot") or {}
        pending = (snapshot.get("pending_work") or "").strip()
        if not next_action.get("text") and not pending:
            continue
        evidence = [f"workspace status = {status}"]
        if next_action.get("text"):
            evidence.append(f"next_action.text = {next_action['text']!r}")
        if pending:
            evidence.append(f"latest_snapshot.pending_work = {pending[:120]!r}")
        recs.append(
            make_recommendation(
                recommendation="Confirm this paused project's status",
                priority=35,
                confidence=0.8,
                evidence=evidence,
                project=project_ref(
                    item_id=item.get("id"),
                    canonical_project_id=item.get("canonical_project_id"),
                    display_name=item.get("name"),
                ),
                suggested_action="Resume it or explicitly mark it done/archived",
                reason=f"Marked '{status}' but still has open work recorded -- worth an "
                "explicit decision rather than staying paused by default.",
                action_link=f"#/dproject/{item.get('id')}" if item.get("id") else None,
                source="operational_intelligence",
                rule_id="rule_paused_project_with_pending_work",
            )
        )
    return recs


def rule_unblocks_dependents(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """Sprint C8: reads the Project Ecosystem Engine's dependency evidence
    (`bundle["ecosystem_dependencies"]`, PI's own explicit dependency
    declarations -- not re-derived here) to recommend completing a
    project that one or more *other* adopted projects explicitly depend
    on, when that project still has open work. Example: "Complete ROLE OS
    to unblock ROLE Commerce Factory, RoleValdez.com." Every dependent
    named in the recommendation is backed by a real declared dependency
    edge, listed in `evidence`."""
    from app.project_ecosystem.graph import build_graph, dependents_of

    dependency_rels = bundle.get("ecosystem_dependencies") or []
    if not dependency_rels:
        return []

    graph = build_graph(dependency_rels)
    contexts_by_id = {c["id"]: c for c in bundle["all_contexts"] if c.get("id")}

    recs = []
    seen_targets: set[str] = set()
    for rel in dependency_rels:
        target_ref = rel["target_project"]
        target_id = target_ref.get("canonical_project_id")
        if not target_id or target_id in seen_targets:
            continue
        seen_targets.add(target_id)

        dependents = dependents_of(graph, target_id)
        if not dependents:
            continue
        target_context = contexts_by_id.get(target_id)
        if not target_context:
            continue
        next_action = target_context.get("next_action") or {}
        if not next_action.get("text"):
            continue

        dependent_names = sorted({d["source_project"]["display_name"] for d in dependents})
        recs.append(
            make_recommendation(
                recommendation=f"Complete {target_context['display_name']} to unblock "
                f"{', '.join(dependent_names)}",
                priority=60,
                confidence=0.7,
                evidence=[
                    f"{name} explicitly depends on {target_context['display_name']}"
                    for name in dependent_names
                ],
                project=project_ref(
                    item_id=target_context.get("item_id"),
                    canonical_project_id=target_context.get("id"),
                    display_name=target_context.get("display_name"),
                ),
                suggested_action=next_action.get("text"),
                reason=f"{len(dependent_names)} project(s) declare an explicit dependency on this "
                "one -- finishing its open work unblocks them.",
                action_link=(
                    f"#/dproject/{target_context.get('item_id')}"
                    if target_context.get("item_id")
                    else f"#/project/{target_context.get('id')}"
                ),
                source="operational_intelligence",
                rule_id="rule_unblocks_dependents",
            )
        )
    return recs


# A high-impact-change caution needs a real, multi-project blast radius --
# below this, `rule_unblocks_dependents` above already covers the single-
# or-zero-dependent case (and only when there's open work to point at);
# this rule is about *any* change, once enough other projects are
# entangled with it to warrant "schedule accordingly."
_HIGH_IMPACT_MIN_AFFECTED = 2
# Bounded transitive traversal -- same depth Sprint C9's Impact Analysis
# Engine uses by default, kept here as a plain local constant (not
# imported from `app.impact_analysis`) so Operational Intelligence never
# depends on the heavier engine, only on the Ecosystem Engine's own cheap
# dependency edges already in `bundle["ecosystem_dependencies"]`.
_HIGH_IMPACT_MAX_DEPTH = 3


def rule_high_impact_change(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """Sprint C9: "changing this project today will affect N other
    projects -- schedule accordingly." Reads only the cheap dependency-
    only relationships already in `bundle["ecosystem_dependencies"]`
    (Sprint C8, plain SQL) and does its own bounded, cycle-safe traversal
    of *dependents* (direct + transitive) -- never calls the full Impact
    Analysis Engine (which also reads Assets/Knowledge), preserving this
    engine's own "no repeated scans" contract."""
    from app.project_ecosystem.graph import build_graph, dependents_of

    dependency_rels = bundle.get("ecosystem_dependencies") or []
    if not dependency_rels:
        return []

    graph = build_graph(dependency_rels)
    contexts_by_id = {c["id"]: c for c in bundle["all_contexts"] if c.get("id")}

    def _key(ref: dict[str, Any]) -> str:
        return (
            ref.get("canonical_project_id") or ref.get("item_id") or ref.get("display_name") or ""
        )

    recs = []
    seen_projects: set[str] = set()
    for rel in dependency_rels:
        target_id = rel["target_project"].get("canonical_project_id")
        if not target_id or target_id in seen_projects:
            continue
        seen_projects.add(target_id)

        visited = {target_id}
        frontier = [target_id]
        affected_names: list[str] = []
        for _depth in range(_HIGH_IMPACT_MAX_DEPTH):
            next_frontier = []
            for key in frontier:
                for dep_rel in dependents_of(graph, key):
                    dependent_key = _key(dep_rel["source_project"])
                    if dependent_key in visited:
                        continue
                    visited.add(dependent_key)
                    affected_names.append(dep_rel["source_project"]["display_name"])
                    next_frontier.append(dependent_key)
            frontier = next_frontier
            if not frontier:
                break

        if len(affected_names) < _HIGH_IMPACT_MIN_AFFECTED:
            continue
        target_context = contexts_by_id.get(target_id)
        if not target_context:
            continue

        recs.append(
            make_recommendation(
                recommendation=f"Changing {target_context['display_name']} today will affect "
                f"{len(affected_names)} project(s)",
                priority=55,
                confidence=0.7,
                evidence=[
                    f"{name} depends (directly or transitively) on {target_context['display_name']}"
                    for name in affected_names
                ],
                project=project_ref(
                    item_id=target_context.get("item_id"),
                    canonical_project_id=target_context.get("id"),
                    display_name=target_context.get("display_name"),
                ),
                suggested_action="Schedule this change and notify affected project owners",
                reason=f"{len(affected_names)} project(s) depend on this one, directly or "
                "transitively -- a change here has a real blast radius.",
                action_link=(
                    f"#/dproject/{target_context.get('item_id')}"
                    if target_context.get("item_id")
                    else f"#/project/{target_context.get('id')}"
                ),
                source="operational_intelligence",
                rule_id="rule_high_impact_change",
            )
        )
    return recs


ALL_RULES: tuple[Any, ...] = (
    rule_discovery_scan_stale,
    rule_knowledge_stale,
    rule_paused_project_with_pending_work,
    rule_unblocks_dependents,
    rule_high_impact_change,
)
