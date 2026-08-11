"""Assembles Project Memory for one project. Pure composition -- every
field is read from `ProjectContext`'s already-computed builder
(`app.project_context.builder`), Sprint C6's Operational Intelligence
Engine (Operational Recommendation), or Sprint C8's Project Ecosystem
Engine (Related Projects). Nothing here re-derives health, git status,
next action, recommendation priority, or relationships.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings
from app.project_memory.session_intent import build_session_intent
from app.project_memory.summary import build_project_summary

_MAX_COMMIT_SUMMARY_CHARS = 200
_MAX_RELATED_PROJECTS_PER_SECTION = 3
_DEFAULT_OBJECTIVE = "Continue this project"

_ROADMAP_MAX_READ_BYTES = 20_000
_ROADMAP_ACTIVE_MARKER_RE = re.compile(r"🟢|\bactive\b", re.IGNORECASE)
_ROADMAP_INACTIVE_RE = re.compile(r"\binactive\b", re.IGNORECASE)
# A literal "Phase N" reference -- not just any line containing "active",
# which would otherwise match a document's own top-level "**Status:**
# Active" metadata line before ever reaching a real phase.
_ROADMAP_PHASE_HEADING_RE = re.compile(r"phase\s*\d", re.IGNORECASE)


def _is_phase_table_row(stripped: str) -> bool:
    """A markdown table row whose *first* cell is a bare phase number
    (`| 1 | Foundation | 🟢 Active | ... |`) -- deliberately excludes a
    status-legend table explaining what the emoji means
    (`| 🟢 Active | Currently being executed |`), whose first cell is the
    marker itself, not a phase number."""
    if "|" not in stripped:
        return False
    cells = [c.strip() for c in stripped.strip("|").split("|") if c.strip()]
    return bool(cells) and cells[0].isdigit()


def _where_we_left_off(context: dict[str, Any], snapshot: dict[str, Any] | None) -> str:
    """Prefers the human-authored Session Snapshot (a person's own account
    of where things stand) over the mechanically-derived last commit --
    the same "session hint beats filesystem" priority `extract_next_action`
    already applies to Next Action, applied here to this field too."""
    if snapshot:
        text = (snapshot.get("summary") or snapshot.get("accomplishments") or "").strip()
        if text:
            return text
    git = context.get("git") or {}
    commit_message = git.get("last_commit_message")
    commit_date = git.get("last_commit_date")
    if commit_message:
        summary = commit_message.strip()[:_MAX_COMMIT_SUMMARY_CHARS]
        return f"Last commit: {summary}" + (f" ({commit_date})" if commit_date else "")
    return "No prior activity recorded."


def _find_case_insensitive(root: Path, name: str) -> Path | None:
    try:
        for entry in root.iterdir():
            if entry.is_file() and entry.name.lower() == name.lower():
                return entry
    except OSError:
        pass
    return None


def _roadmap_current_phase(root_path: str | None) -> str | None:
    """Current Objective's ROADMAP.md tier -- deliberately reads
    something different from what Next Action's own ROADMAP tier reads
    (`discovery.next_action._from_roadmap` picks the first unchecked
    checklist item, a concrete task). This looks for the phase/row
    already marked active (a status legend's 🟢/"Active" marker, the
    convention this workspace's own ROADMAP.md files use), which answers
    "what phase are we in" rather than "what's the next single item" --
    so the two fields can never collapse into the same text even when
    both happen to read the same file."""
    if not root_path:
        return None
    root = Path(root_path)
    if not root.is_dir():
        return None
    path = _find_case_insensitive(root, "ROADMAP.md")
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            text = fh.read(_ROADMAP_MAX_READ_BYTES)
    except OSError:
        return None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or _ROADMAP_INACTIVE_RE.search(stripped):
            continue
        if not (_is_phase_table_row(stripped) or _ROADMAP_PHASE_HEADING_RE.search(stripped)):
            continue
        if _ROADMAP_ACTIVE_MARKER_RE.search(stripped):
            cells = [c.strip() for c in stripped.strip("|").split("|") if c.strip()]
            return " -- ".join(cells) if len(cells) > 1 else stripped
    return None


def _current_objective(display_name: str, context: dict[str, Any], settings: Settings) -> str:
    """Distinct from Next Action -- deliberately never reads
    NEXT_ACTION.md/TODO.md/the Operational Intelligence recommendation
    (Next Action's own sources), so the two fields can never accidentally
    collapse into identical text (the exact bug real-world Resume Work
    validation found: both used to read `next_action.get("text")`).
    Priority: the most recent Daily Session's own human-authored
    objective for this project ("Project Memory" -- `app.session`'s
    `sessions.objective`) -> ROADMAP.md's active-phase marker -> the
    honest default, never invented prose from a file that doesn't
    actually say what today's objective is.

    The Daily Session domain (`app.session`, ROLE OS v1.0's "Dashboard
    MVP") predates Project Intelligence/canonical projects and keys its
    own `registry_projects`/`sessions.project_id` by a separate, hand-
    seeded slug ("role-os", not a canonical UUID) -- there is no shared
    id space to join on. Matched by display name instead, case-
    insensitively, the same soft cross-domain match convention this
    module already uses for Knowledge cards (`_knowledge_count`)."""
    from app.session import db as session_db

    name_lower = (display_name or "").strip().lower()
    if name_lower:
        for daily_session in session_db.list_sessions(limit=30, settings=settings):
            if (
                daily_session.get("project_name") or ""
            ).strip().lower() == name_lower and daily_session.get("objective"):
                return daily_session["objective"]

    roadmap_phase = _roadmap_current_phase(context.get("root_path"))
    if roadmap_phase:
        return roadmap_phase

    return _DEFAULT_OBJECTIVE


def _next_action_output(
    next_action: dict[str, Any], recommendation: dict[str, Any] | None
) -> dict[str, Any]:
    """The `next_action` field's own fallback chain, for display: `app.
    discovery.next_action.extract_next_action` (NEXT_ACTION.md -> TODO.md
    -> ROADMAP.md, already computed on `context`) -> the Operational
    Intelligence recommendation's `suggested_action` (added by this
    hotfix -- previously Next Action had no Operational Intelligence
    fallback at all, so a project with no file-based signal always
    rendered "None recorded." even with a real recommendation available)
    -> honest empty. Never reads the Daily Session objective
    `_current_objective` reads, so the two fields never share a source."""
    if next_action.get("text"):
        return next_action
    if recommendation and recommendation.get("suggested_action"):
        return {
            **next_action,
            "text": recommendation["suggested_action"],
            "source": "operational_intelligence",
        }
    return next_action


def _pending_work(
    snapshot: dict[str, Any] | None,
    next_action: dict[str, Any],
    recommendation: dict[str, Any] | None,
) -> str:
    """Hotfix following real-world Resume Work validation: this used to
    read *only* the AI Session Snapshot's own `pending_work` field, so
    any project without a recent snapshot honestly (but unhelpfully)
    reported "None recorded." even when real open work was sitting in
    ROADMAP.md/TODO.md/NEXT_ACTION.md. Priority: the snapshot's own
    human-authored account (unchanged, still first) -- then Project
    Memory's own already-computed Next Action (`discovery.next_action.
    extract_next_action`'s own ROADMAP.md -> TODO.md -> NEXT_ACTION.md
    priority chain, reused here rather than re-reading the same files a
    second time) -- then the Operational Intelligence recommendation for
    this project, already computed once by `build_project_memory`.
    Never invents a value; `""` (rendered as "None recorded.") only when
    every one of these is genuinely empty."""
    snapshot_pending = (snapshot or {}).get("pending_work")
    if snapshot_pending:
        return snapshot_pending
    if next_action.get("text"):
        return f"{next_action['text']} (source: {next_action.get('source', 'unknown')})"
    if recommendation:
        return f"{recommendation['recommendation']} -- {recommendation['reason']}"
    return ""


def _resolve_context_and_all_contexts(
    canonical_project_id: str, settings: Settings, *, need_all_contexts: bool
) -> tuple[dict[str, Any] | None, list[dict[str, Any]] | None, list[dict[str, Any]] | None]:
    """Resolves this project's context, and -- only when a caller actually
    needs the whole-workspace list (for Operational Intelligence and/or
    Related Projects) -- the `all_project_contexts()` result too, computed
    at most once and reused everywhere, never twice in one
    `build_project_memory` call."""
    from app.project_context.builder import build_project_context

    if not need_all_contexts:
        context = build_project_context(
            project_id=canonical_project_id,
            settings=settings,
            include_resume_state=False,
            include_epic2_recs=False,
        )
        return context, None, None

    from app.project_context.builder import all_project_contexts

    all_contexts, enriched_items = all_project_contexts(settings=settings)
    context = next((c for c in all_contexts if c.get("id") == canonical_project_id), None)
    if context is None:
        # A canonical project that hasn't surfaced in the bulk "every
        # tracked project" list yet (edge case -- e.g. a brand-new manual
        # project) -- fall back to the single-project builder rather than
        # returning nothing.
        context = build_project_context(
            project_id=canonical_project_id,
            settings=settings,
            include_resume_state=False,
            include_epic2_recs=False,
        )
    return context, all_contexts, enriched_items


def _top_recommendation(
    canonical_project_id: str, operational_intelligence_recs: list[dict[str, Any]]
) -> dict[str, Any] | None:
    return next(
        (
            r
            for r in operational_intelligence_recs
            if (r.get("project") or {}).get("canonical_project_id") == canonical_project_id
        ),
        None,
    )


def _related_projects_and_impact(
    canonical_project_id: str,
    all_contexts: list[dict[str, Any]],
    enriched_items: list[dict[str, Any]],
    settings: Settings,
    *,
    operational_intelligence_recs: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Small, bounded sections only -- top dependencies/consumers/shared-
    knowledge project names, and a one-line Potential Impact summary --
    never a graph dump. Computes the Project Ecosystem Engine's
    relationship set exactly once and threads it into both
    `get_project_ecosystem` (Related Projects) and `get_impact_analysis`
    (Potential Impact, Sprint C9) -- neither re-runs the detector
    registry or rebuilds the graph a second time. `operational_
    intelligence_recs` (already computed once by `build_project_memory`
    for the Operational Recommendation field) is threaded into `get_
    impact_analysis` too, so Operational Intelligence is never computed
    twice in one `build_project_memory` call."""
    from app.impact_analysis import get_impact_analysis
    from app.project_ecosystem import compute_relationships, get_project_ecosystem

    relationships = compute_relationships(all_contexts=all_contexts, settings=settings)
    ecosystem = get_project_ecosystem(
        canonical_project_id,
        settings=settings,
        all_contexts=all_contexts,
        relationships=relationships,
    )
    impact = get_impact_analysis(
        canonical_project_id,
        settings=settings,
        all_contexts=all_contexts,
        enriched_items=enriched_items,
        relationships=relationships,
        operational_intelligence_recs=operational_intelligence_recs,
    )

    def _names(rels: list[dict[str, Any]], other_side: str) -> list[str]:
        seen: list[str] = []
        for rel in rels[:_MAX_RELATED_PROJECTS_PER_SECTION]:
            name = rel[other_side]["display_name"]
            if name not in seen:
                seen.append(name)
        return seen

    related_projects = (
        {
            "dependencies": _names(ecosystem["dependencies"], "target_project"),
            "consumers": _names(ecosystem["consumers"], "source_project"),
            "recent_shared_decisions": _names(ecosystem["shared_knowledge"], "target_project"),
        }
        if ecosystem is not None
        else {"dependencies": [], "consumers": [], "recent_shared_decisions": []}
    )

    potential_impact = (
        {
            "overall_risk": impact["overall_risk"],
            "affected_count": len(impact["affected_projects"]),
            "affected_names": [
                p["display_name"]
                for p in impact["affected_projects"][:_MAX_RELATED_PROJECTS_PER_SECTION]
            ],
            "top_reason": (
                impact["evidence"][0] if impact["evidence"] else "No supporting evidence yet."
            ),
        }
        if impact is not None
        else {"overall_risk": "none", "affected_count": 0, "affected_names": [], "top_reason": ""}
    )

    return related_projects, potential_impact


def build_project_memory(
    canonical_project_id: str,
    settings: Settings | None = None,
    *,
    include_operational_recommendation: bool = True,
    include_related_projects: bool = True,
    user_objective: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """`include_operational_recommendation=False`/`include_related_
    projects=False` skip the relatively expensive whole-workspace passes
    (Operational Intelligence, Project Ecosystem, Impact Analysis) -- used
    by `preview_resume_state`, which (unlike Resume Work itself) runs on
    every `ProjectContext` build/page load and must stay cheap; the real
    Resume Work click always includes them (the brief's "Operational
    Recommendation" is a mandatory prompt section; Related Projects/
    Potential Impact are small bounded additions to the same click).
    `include_related_projects` gates both Related Projects and Potential
    Impact (Sprint C9) since both are built from the same Project
    Ecosystem relationship computation. Session Intent (hotfix) piggybacks
    on `include_operational_recommendation` -- it needs the same
    Operational Intelligence/Executive Decision evidence, so it's gated
    the same way rather than adding a third, overlapping cost knob.
    `user_objective` (optional `{requested_action, expected_deliverable,
    completion_criteria}`) is the no-action guard's own answer, once the
    user has supplied one -- when present it wins over every other
    Session Intent source outright."""
    settings = settings or get_settings()
    need_all_contexts = include_operational_recommendation or include_related_projects
    context, all_contexts, enriched_items = _resolve_context_and_all_contexts(
        canonical_project_id, settings, need_all_contexts=need_all_contexts
    )
    if context is None:
        return None

    # Sprint C9: computed at most once, then threaded into both the
    # Operational Recommendation field and `get_impact_analysis`'s
    # operational_effects -- never two separate whole-workspace
    # Operational Intelligence passes for one `build_project_memory` call.
    operational_intelligence_recs = None
    if (
        include_operational_recommendation or include_related_projects
    ) and all_contexts is not None:
        from app.operational_intelligence import get_operational_intelligence

        operational_intelligence_recs = get_operational_intelligence(
            settings=settings, all_contexts=all_contexts, enriched_items=enriched_items
        )

    recommendation = (
        _top_recommendation(canonical_project_id, operational_intelligence_recs)
        if include_operational_recommendation and operational_intelligence_recs is not None
        else None
    )
    if include_related_projects and all_contexts is not None:
        related_projects, potential_impact = _related_projects_and_impact(
            canonical_project_id,
            all_contexts,
            enriched_items,
            settings,
            operational_intelligence_recs=operational_intelligence_recs or [],
        )
    else:
        related_projects = {"dependencies": [], "consumers": [], "recent_shared_decisions": []}
        potential_impact = {
            "overall_risk": "none",
            "affected_count": 0,
            "affected_names": [],
            "top_reason": "",
        }

    next_action = context.get("next_action") or {}
    snapshot = context.get("latest_snapshot")
    next_action_output = _next_action_output(next_action, recommendation)

    session_intent = (
        build_session_intent(
            context,
            settings,
            recommendation=recommendation,
            next_action_output=next_action_output,
            user_objective=user_objective,
        )
        if include_operational_recommendation
        else None
    )

    return {
        "project_id": canonical_project_id,
        "project_name": context.get("display_name") or "Untitled Project",
        "project_summary": build_project_summary(context),
        "current_objective": _current_objective(
            context.get("display_name") or "", context, settings
        ),
        "where_we_left_off": _where_we_left_off(context, snapshot),
        "pending_work": _pending_work(snapshot, next_action, recommendation),
        "next_action": next_action_output,
        "session_intent": session_intent,
        "operational_recommendation": recommendation,
        "related_projects": related_projects,
        "potential_impact": potential_impact,
        "latest_snapshot": snapshot,
        "latest_ai_session": context.get("latest_ai_session"),
        "git": context.get("git") or {},
        "health": context.get("health"),
        "latest_activity": context.get("latest_activity"),
        # Hotfix (Execution Target): the two fields
        # `app.workspace.execution_target.classify_execution_target` needs
        # to decide Claude Code vs. a web assistant -- already computed by
        # the Discovery Engine, just not previously threaded through to
        # Project Memory's own return shape.
        "root_path": context.get("root_path"),
        "classification": context.get("classification"),
    }
