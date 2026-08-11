"""Explorer 2.0 (Sprint C3): universal search over every domain ROLE OS
already tracks -- Projects, ProjectContext, Workspace items, AI Sessions,
Snapshots, Timeline, Recent Activity, Knowledge Cards, Assets, Commits,
README/ROADMAP/CHANGELOG/TODO markdown, imported ChatGPT conversations,
Decisions, Capabilities, Dependencies, and Advisor recommendations.

This is an aggregation layer, not a new index: every result is produced by
calling an existing, already-tested lookup/search function once (`app.db.
search_cards`, `app.imports.db.list_conversations_page`,
`app.projects.db.list_capabilities(q=...)`, `ProjectContext`, `workspace.
service`/`workspace.advisor`, `workspace.assets_index`, `discovery`'s own
README/ROADMAP/CHANGELOG/TODO detection flags) and normalizing its output
into one common result shape. No new SQLite file, no new table, no
duplicated storage of anything already indexed elsewhere.

Ranking (`_score`) is a small, fully-explainable point system -- exact
match, canonical-project bonus, title/filename/summary substring matches,
a recency bonus, and a modest `ProjectContext`-derived priority bonus
(health score + business value) -- never a hidden weighting, and always
followed by a stable tie-break (type, then title) so identical queries
always return identical ordering.

Deduplication is free: every project-shaped result is built from
`app.projects.db.list_projects()` (which excludes merged rows by default,
Sprint C2.1) or from `ProjectContext` (which resolves through a merge), so
a merged project can never appear twice.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app import db as knowledge_db
from app.advisor import engine as advisor_engine
from app.config import Settings, get_settings
from app.imports import db as imports_db
from app.project_context.builder import all_project_contexts as _all_project_contexts
from app.projects import db as projects_db
from app.workspace import advisor as workspace_advisor
from app.workspace import assets_index
from app.workspace import service as workspace_service

RESULT_TYPES = (
    "Project",
    "AI Session",
    "Snapshot",
    "Commit",
    "Knowledge Card",
    "Asset",
    "Conversation",
    "Markdown",
    "Decision",
    "Capability",
    "Dependency",
    "Recommendation",
    "Timeline Event",
    "Ecosystem Relationship",
    "Impact",
    "Executive Decision",
)

_MARKDOWN_FILES = (
    ("has_readme", "README.md"),
    ("has_roadmap", "ROADMAP.md"),
    ("has_changelog", "CHANGELOG.md"),
    ("has_todo", "TODO.md"),
)
_MARKDOWN_MAX_BYTES = 20_000
_DEFAULT_LIMIT_PER_TYPE = 40


def _project_nav(item_id: str | None, project_id: str | None) -> dict[str, str | None]:
    """The one navigation-target rule every Project-shaped result (and
    everything that belongs to a project) uses: a discovered item opens
    the Discovered Project Detail view, a purely-manual project opens the
    Project Intelligence detail view -- the same routing `dashProjectRef`
    already established for the Dashboard (Sprint C2)."""
    if item_id:
        return {"nav": "dproject", "param": item_id}
    return {"nav": "project", "param": project_id}


def _read_markdown_excerpt(path: Path, query: str) -> str | None:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            text = fh.read(_MARKDOWN_MAX_BYTES)
    except OSError:
        return None
    lower = text.lower()
    idx = lower.find(query.lower()) if query else 0
    if query and idx == -1:
        return None
    start = max(0, idx - 60)
    excerpt = text[start : start + 200].strip()
    return excerpt or None


def _search_projects(query: str, contexts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    for ctx in contexts:
        haystack = " ".join(
            filter(
                None,
                [ctx.get("display_name"), ctx.get("classification"), ctx.get("root_path")]
                + (ctx.get("technology_stack") or []),
            )
        )
        if query and query.lower() not in haystack.lower():
            continue
        actions = [{"label": "Open Project", **_project_nav(ctx.get("item_id"), ctx.get("id"))}]
        if (ctx.get("resume_state") or {}).get("available"):
            actions.append(
                {"label": "Resume Work", "action": "resume", "param": ctx.get("item_id")}
            )
        results.append(
            {
                "type": "Project",
                "id": ctx["id"],
                "title": ctx["display_name"],
                "project": ctx["display_name"],
                "project_id": ctx["id"],
                "item_id": ctx.get("item_id"),
                "summary": (ctx.get("next_action") or {}).get("text")
                or ctx.get("classification")
                or "",
                "date": ctx.get("latest_activity"),
                "origin": (
                    "Discovered project" if ctx.get("is_discovered") else "Project Intelligence"
                ),
                "actions": actions,
                "_title_exact": query.lower() == ctx["display_name"].lower() if query else False,
                "_is_canonical": True,
                "_health_score": ctx.get("health_score") or 0,
                "_business_value": ctx.get("business_value"),
            }
        )
    return results


def _search_ai_sessions_and_snapshots(
    query: str, contexts: list[dict[str, Any]], settings: Settings
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sessions_out, snapshots_out = [], []
    for ctx in contexts:
        project_id = ctx["id"]
        sessions = projects_db.list_ai_sessions(project_id, settings=settings)
        for s in sessions:
            haystack = " ".join(
                filter(None, [s.get("title"), s.get("assistant"), s.get("role"), s.get("notes")])
            )
            if not query or query.lower() in haystack.lower():
                sessions_out.append(
                    {
                        "type": "AI Session",
                        "id": s["id"],
                        "title": s.get("title") or f"{s.get('assistant', 'AI')} session",
                        "project": ctx["display_name"],
                        "project_id": project_id,
                        "item_id": ctx.get("item_id"),
                        "summary": s.get("notes") or s.get("assistant") or "",
                        "date": s.get("last_used_at") or s.get("started_at"),
                        "origin": f"{s.get('assistant', '')} session".strip(),
                        "actions": [
                            {"label": "Open Session", "nav": "cockpit", "param": project_id}
                        ],
                        "_title_exact": False,
                        "_is_canonical": True,
                        "_health_score": ctx.get("health_score") or 0,
                        "_business_value": ctx.get("business_value"),
                    }
                )
            snapshots = projects_db.list_ai_session_snapshots(s["id"], settings=settings)
            for snap in snapshots:
                haystack = " ".join(
                    filter(
                        None,
                        [
                            snap.get("accomplishments"),
                            snap.get("blockers"),
                            snap.get("pending_work"),
                            snap.get("next_prompt"),
                            snap.get("decisions"),
                            snap.get("summary"),
                        ],
                    )
                )
                if query and query.lower() not in haystack.lower():
                    continue
                snapshots_out.append(
                    {
                        "type": "Snapshot",
                        "id": snap["id"],
                        "title": snap.get("summary") or "Session snapshot",
                        "project": ctx["display_name"],
                        "project_id": project_id,
                        "item_id": ctx.get("item_id"),
                        "summary": snap.get("pending_work") or snap.get("next_prompt") or "",
                        "date": snap.get("created_at"),
                        "origin": "AI session snapshot",
                        "actions": [
                            {"label": "Open Session", "nav": "cockpit", "param": project_id}
                        ],
                        "_title_exact": False,
                        "_is_canonical": True,
                        "_health_score": ctx.get("health_score") or 0,
                        "_business_value": ctx.get("business_value"),
                    }
                )
    return sessions_out, snapshots_out


def _search_commits(query: str, contexts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    for ctx in contexts:
        for commit in ctx.get("commits") or []:
            message = commit.get("message") or ""
            if query and query.lower() not in message.lower():
                continue
            results.append(
                {
                    "type": "Commit",
                    "id": commit.get("hash") or f"{ctx['id']}-{commit.get('date')}",
                    "title": message.splitlines()[0][:120] if message else "(no message)",
                    "project": ctx["display_name"],
                    "project_id": ctx["id"],
                    "item_id": ctx.get("item_id"),
                    "summary": message,
                    "date": commit.get("date"),
                    "origin": "git commit",
                    "actions": [
                        {"label": "Open Project", **_project_nav(ctx.get("item_id"), ctx["id"])}
                    ],
                    "_title_exact": False,
                    "_is_canonical": True,
                    "_health_score": ctx.get("health_score") or 0,
                    "_business_value": ctx.get("business_value"),
                }
            )
    return results


def _search_markdown(query: str, contexts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    for ctx in contexts:
        root_path = ctx.get("root_path")
        if not root_path:
            continue
        root = Path(root_path)
        if not root.is_dir():
            continue
        for flag_key, filename in _MARKDOWN_FILES:
            path = root / filename
            if not path.is_file():
                continue
            keyword_match = query and query.lower() in filename.lower()
            excerpt = _read_markdown_excerpt(path, query) if query and not keyword_match else None
            if query and not keyword_match and excerpt is None:
                continue
            results.append(
                {
                    "type": "Markdown",
                    "id": f"{ctx['id']}-{filename}",
                    "title": filename,
                    "project": ctx["display_name"],
                    "project_id": ctx["id"],
                    "item_id": ctx.get("item_id"),
                    "summary": excerpt or f"{filename} in {ctx['display_name']}",
                    "date": ctx.get("latest_activity"),
                    "origin": filename,
                    "actions": [
                        {"label": "Open Project", **_project_nav(ctx.get("item_id"), ctx["id"])}
                    ],
                    "_title_exact": query.lower() == filename.lower() if query else False,
                    "_is_canonical": True,
                    "_health_score": ctx.get("health_score") or 0,
                    "_business_value": ctx.get("business_value"),
                    "_filename_match": keyword_match,
                }
            )
    return results


def _search_assets(
    query: str, contexts: list[dict[str, Any]], settings: Settings
) -> list[dict[str, Any]]:
    """Sprint C4 (Assets OS): delegates to the canonical `app.assets.
    service.list_all_assets` -- the same index the Assets gallery and
    Project Hub use -- instead of walking each project's filesystem a
    second time here. An Explorer asset result's primary action opens the
    real Asset Detail panel (`nav: "asset"`), not a legacy file
    representation; there is no second asset mapper."""
    from app.assets.service import list_all_assets as _list_all_assets

    contexts_by_id = {c["id"]: c for c in contexts}
    results = []
    for r in _list_all_assets(settings=settings):
        haystack = f"{r.filename} {r.category} {r.project}"
        if query and query.lower() not in haystack.lower():
            continue
        ctx = contexts_by_id.get(r.canonical_project_id) if r.canonical_project_id else None
        results.append(
            {
                "type": "Asset",
                "id": r.asset_id,
                "title": r.filename,
                "project": r.project,
                "project_id": r.canonical_project_id,
                "item_id": r.discovery_item_id,
                "summary": r.category,
                "date": r.modified_at,
                "origin": "discovered asset",
                "actions": [
                    {"label": "Open Asset", "nav": "asset", "param": r.asset_id},
                    {
                        "label": "Open Project",
                        **_project_nav(r.discovery_item_id, r.canonical_project_id),
                    },
                ],
                "_title_exact": query.lower() == r.filename.lower() if query else False,
                "_is_canonical": True,
                "_health_score": (ctx or {}).get("health_score") or 0,
                "_business_value": (ctx or {}).get("business_value"),
                "_filename_match": bool(query) and query.lower() in r.filename.lower(),
            }
        )
    return results


_TIMELINE_EVENT_ACTIVITY_TYPES = {"adopted", "filesystem_modified"}


def _search_timeline_events(
    query: str, contexts: list[dict[str, Any]], settings: Settings
) -> list[dict[str, Any]]:
    """Reuses `workspace.service.list_activity_feed` (already deduplicated)
    for the event kinds not already covered by a more specific result type
    -- `git_commit` has its own `Commit` type (§ `_search_commits`, sourced
    from `ProjectContext.commits`) and `ai_session`/`ai_snapshot` have
    their own richer `AI Session`/`Snapshot` types (§ `_search_ai_sessions_
    and_snapshots`, sourced directly from the DB rather than the feed's
    summary strings) -- surfacing them again here would just be the same
    events under a second label."""
    contexts_by_item_id = {c["item_id"]: c for c in contexts if c.get("item_id")}
    events = workspace_service.list_activity_feed(limit=200, settings=settings)
    results = []
    for e in events:
        if e["type"] not in _TIMELINE_EVENT_ACTIVITY_TYPES:
            continue
        haystack = f"{e.get('summary', '')} {e.get('project_name', '')}"
        if query and query.lower() not in haystack.lower():
            continue
        ctx = contexts_by_item_id.get(e["project_id"])
        results.append(
            {
                "type": "Timeline Event",
                "id": f"{e['type']}-{e['project_id']}-{e['timestamp']}",
                "title": e.get("summary") or e["type"],
                "project": e.get("project_name"),
                "project_id": ctx["id"] if ctx else None,
                "item_id": ctx.get("item_id") if ctx else e.get("project_id"),
                "summary": e.get("summary") or "",
                "date": e.get("timestamp"),
                "origin": e["type"].replace("_", " "),
                "actions": [
                    {
                        "label": "Open Project",
                        **_project_nav(
                            ctx.get("item_id") if ctx else e.get("project_id"),
                            ctx["id"] if ctx else None,
                        ),
                    }
                ],
                "_title_exact": False,
                "_is_canonical": True,
                "_health_score": (ctx or {}).get("health_score") or 0,
                "_business_value": (ctx or {}).get("business_value"),
            }
        )
    return results


def _search_knowledge(query: str, settings: Settings) -> list[dict[str, Any]]:
    if not query:
        return []
    try:
        cards = knowledge_db.search_cards(query, settings=settings, limit=_DEFAULT_LIMIT_PER_TYPE)
    except Exception:
        return []
    return [
        {
            "type": "Knowledge Card",
            "id": c["conversation_id"],
            "title": c["title"],
            "project": c.get("project"),
            "project_id": None,
            "item_id": None,
            "summary": c.get("summary") or "",
            "date": c.get("updated") or c.get("date"),
            "origin": f"{c.get('category', '')} knowledge card".strip(),
            "actions": [{"label": "Open Knowledge", "nav": "card", "param": c["conversation_id"]}],
            "_title_exact": query.lower() == c["title"].lower(),
            "_is_canonical": False,
            "_health_score": 0,
            "_business_value": None,
        }
        for c in cards
    ]


def _search_conversations(query: str, settings: Settings) -> list[dict[str, Any]]:
    if not query:
        return []
    items, _total = imports_db.list_conversations_page(
        q=query, page=1, page_size=_DEFAULT_LIMIT_PER_TYPE, settings=settings
    )
    return [
        {
            "type": "Conversation",
            "id": c["id"],
            "title": c["title"] or "(untitled conversation)",
            "project": None,
            "project_id": None,
            "item_id": None,
            "summary": c.get("source") or "",
            "date": c.get("imported_at"),
            "origin": f"imported {c.get('source', 'conversation')}",
            "actions": [
                {"label": "Open Conversation", "nav": "explorer-conversation", "param": c["id"]}
            ],
            "_title_exact": query.lower() == (c["title"] or "").lower(),
            "_is_canonical": False,
            "_health_score": 0,
            "_business_value": None,
        }
        for c in items
    ]


def _search_decisions(
    query: str, contexts: list[dict[str, Any]], settings: Settings
) -> list[dict[str, Any]]:
    results = []
    for ctx in contexts:
        project = projects_db.get_project(ctx["id"], settings=settings)
        if not project:
            continue
        for d in project.get("decisions") or []:
            text = d.get("text") or ""
            if query and query.lower() not in text.lower():
                continue
            results.append(
                {
                    "type": "Decision",
                    "id": d["id"],
                    "title": text[:120] or "(untitled decision)",
                    "project": ctx["display_name"],
                    "project_id": ctx["id"],
                    "item_id": ctx.get("item_id"),
                    "summary": text,
                    "date": d.get("created_at"),
                    "origin": "project decision",
                    "actions": [
                        {"label": "Open Project", **_project_nav(ctx.get("item_id"), ctx["id"])}
                    ],
                    "_title_exact": False,
                    "_is_canonical": True,
                    "_health_score": ctx.get("health_score") or 0,
                    "_business_value": ctx.get("business_value"),
                }
            )
    return results


def _search_capabilities_and_dependencies(
    query: str, contexts: list[dict[str, Any]], settings: Settings
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    contexts_by_id = {c["id"]: c for c in contexts}
    caps = projects_db.list_capabilities(q=query or None, settings=settings)
    cap_results = []
    for cap in caps:
        ctx = contexts_by_id.get(cap["project_id"])
        project_name = ctx["display_name"] if ctx else None
        cap_results.append(
            {
                "type": "Capability",
                "id": cap["id"],
                "title": cap["name"],
                "project": project_name,
                "project_id": cap["project_id"],
                "item_id": ctx.get("item_id") if ctx else None,
                "summary": cap.get("description") or cap.get("category") or "",
                "date": cap.get("created_at"),
                "origin": "capability",
                "actions": [
                    {
                        "label": "Open Project",
                        **_project_nav(ctx.get("item_id") if ctx else None, cap["project_id"]),
                    }
                ],
                "_title_exact": query.lower() == cap["name"].lower() if query else False,
                "_is_canonical": True,
                "_health_score": (ctx or {}).get("health_score") or 0,
                "_business_value": (ctx or {}).get("business_value"),
            }
        )

    dep_results = []
    for ctx in contexts:
        for dep in projects_db.list_dependencies(ctx["id"], settings=settings):
            haystack = f"{dep.get('note', '')} {dep.get('depends_on_project_name', '')}"
            if query and query.lower() not in haystack.lower():
                continue
            dep_results.append(
                {
                    "type": "Dependency",
                    "id": dep["id"],
                    "title": f"{ctx['display_name']} depends on {dep.get('depends_on_project_name', '?')}",
                    "project": ctx["display_name"],
                    "project_id": ctx["id"],
                    "item_id": ctx.get("item_id"),
                    "summary": dep.get("note") or "",
                    "date": dep.get("created_at"),
                    "origin": "dependency",
                    "actions": [
                        {"label": "Open Project", **_project_nav(ctx.get("item_id"), ctx["id"])}
                    ],
                    "_title_exact": False,
                    "_is_canonical": True,
                    "_health_score": ctx.get("health_score") or 0,
                    "_business_value": ctx.get("business_value"),
                }
            )
    return cap_results, dep_results


def _search_recommendations(
    query: str,
    contexts: list[dict[str, Any]],
    enriched_items: list[dict[str, Any]],
    settings: Settings,
) -> list[dict[str, Any]]:
    contexts_by_item_id = {c["item_id"]: c for c in contexts if c.get("item_id")}
    results = []
    for rec in workspace_advisor.generate_recommendations(enriched_items):
        haystack = f"{rec.get('recommendation', '')} {rec.get('reason', '')}"
        if query and query.lower() not in haystack.lower():
            continue
        ctx = contexts_by_item_id.get(rec["project_id"])
        results.append(
            {
                "type": "Recommendation",
                "id": f"ws-{rec['project_id']}-{rec['recommendation'][:30]}",
                "title": rec["recommendation"],
                "project": rec.get("project"),
                "project_id": ctx["id"] if ctx else None,
                "item_id": rec.get("item_id"),
                "summary": rec.get("reason") or "",
                "evidence": rec.get("evidence") or [],
                "date": None,
                "origin": "Workspace Advisor",
                "actions": [
                    {
                        "label": "Open Project",
                        **_project_nav(rec.get("item_id"), ctx["id"] if ctx else None),
                    }
                ],
                "_title_exact": False,
                "_is_canonical": True,
                "_health_score": (ctx or {}).get("health_score") or 0,
                "_business_value": (ctx or {}).get("business_value"),
            }
        )

    manual_project_ids = [c["id"] for c in contexts if not c.get("item_id")]
    for project_id in manual_project_ids:
        try:
            epic2_recs = advisor_engine.get_recommendations(
                project_id=project_id, settings=settings
            )
        except Exception:
            epic2_recs = []
        ctx = next((c for c in contexts if c["id"] == project_id), None)
        for rec in epic2_recs:
            haystack = f"{rec.get('title', '')} {rec.get('reason', '')}"
            if query and query.lower() not in haystack.lower():
                continue
            results.append(
                {
                    "type": "Recommendation",
                    "id": rec.get("id") or f"pi-{project_id}-{rec.get('title', '')[:30]}",
                    "title": rec.get("title") or rec.get("suggested_action") or "Recommendation",
                    "project": ctx["display_name"] if ctx else None,
                    "project_id": project_id,
                    "item_id": None,
                    "summary": rec.get("reason") or "",
                    "evidence": rec.get("evidence") or [],
                    "date": rec.get("created_at"),
                    "origin": "Advisor",
                    "actions": [{"label": "Open Project", **_project_nav(None, project_id)}],
                    "_title_exact": False,
                    "_is_canonical": True,
                    "_health_score": (ctx or {}).get("health_score") or 0,
                    "_business_value": (ctx or {}).get("business_value"),
                }
            )
    return results


# Sprint C8: relationship-type keywords a search query can match, mapped to
# the canonical `relationship_type` values `app.project_ecosystem.models`
# defines -- no new vocabulary, just synonyms for the same fixed enum.
_ECOSYSTEM_TYPE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "shares_assets": ("shared asset", "shares asset"),
    "shares_knowledge": ("shared knowledge", "shares knowledge"),
    "shares_documentation": ("shared documentation", "shares documentation", "shared docs"),
    "shares_prompts": ("shared prompt", "shares prompt"),
    "shares_sessions": ("shared session", "shares session"),
    "depends_on": ("depends on", "dependency", "dependencies"),
    "blocks": ("blocks", "blocked by", "blocked_by"),
}


def _ecosystem_result(
    rel: dict[str, Any], *, title: str, project_ref: dict[str, Any]
) -> dict[str, Any]:
    return {
        "type": "Ecosystem Relationship",
        "id": rel["relationship_id"],
        "title": title,
        "project": project_ref.get("display_name"),
        "project_id": project_ref.get("canonical_project_id"),
        "item_id": project_ref.get("item_id"),
        "summary": "; ".join(rel["evidence"]),
        "date": rel.get("discovered_at"),
        "origin": "Project Ecosystem",
        "evidence": rel["evidence"],
        "actions": [
            {
                "label": "Open Project",
                **_project_nav(project_ref.get("item_id"), project_ref.get("canonical_project_id")),
            }
        ],
        "_title_exact": False,
        "_is_canonical": True,
        "_health_score": 0,
        "_business_value": None,
    }


def _search_ecosystem(
    query: str,
    contexts: list[dict[str, Any]],
    settings: Settings,
    *,
    relationships: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Sprint C8: two search behaviors over the Project Ecosystem Engine's
    already-computed relationships (`relationships`, computed once by
    `search()` and shared with `_search_impact` below -- never a second
    detection pass) -- searching a project name surfaces "Used by ..."
    (who depends on it); searching a relationship-type keyword (e.g.
    "shared assets") surfaces every relationship of that type."""
    from app.project_ecosystem.graph import build_graph, dependents_of

    query_lower = query.strip().lower()
    if not query_lower:
        return []

    results: list[dict[str, Any]] = []

    matched_context = next(
        (c for c in contexts if query_lower in (c.get("display_name") or "").lower()), None
    )
    if matched_context is not None:
        graph = build_graph(relationships)
        for rel in dependents_of(graph, matched_context.get("id")):
            dependent_ref = rel["source_project"]
            results.append(
                _ecosystem_result(
                    rel, title=f"Used by {dependent_ref['display_name']}", project_ref=dependent_ref
                )
            )

    for relationship_type, keywords in _ECOSYSTEM_TYPE_KEYWORDS.items():
        if not any(kw in query_lower for kw in keywords):
            continue
        for rel in relationships:
            if rel["relationship_type"] != relationship_type:
                continue
            title = (
                f"{rel['source_project']['display_name']} ↔ "
                f"{rel['target_project']['display_name']} ({relationship_type})"
            )
            results.append(_ecosystem_result(rel, title=title, project_ref=rel["source_project"]))

    return results


def _search_impact(
    query: str,
    contexts: list[dict[str, Any]],
    settings: Settings,
    *,
    relationships: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Sprint C9: searching a project name also surfaces one "Impact"
    result summarizing what the Impact Analysis Engine found for it --
    reuses the same `relationships` `_search_ecosystem` already has,
    never a second relationship-detection pass or graph build for the
    same request."""
    from app.impact_analysis import get_impact_analysis

    query_lower = query.strip().lower()
    if not query_lower:
        return []

    matched_context = next(
        (c for c in contexts if query_lower in (c.get("display_name") or "").lower()), None
    )
    if matched_context is None:
        return []

    report = get_impact_analysis(
        matched_context["id"], settings=settings, all_contexts=contexts, relationships=relationships
    )
    if report is None or not report["affected_projects"]:
        return []

    affected_names = [p["display_name"] for p in report["affected_projects"]]
    summary_parts = [f"{len(affected_names)} project(s) affected: {', '.join(affected_names)}"]
    if report["shared_assets"]:
        summary_parts.append(f"{len(report['shared_assets'])} shared asset relationship(s)")
    if report["shared_documentation"]:
        summary_parts.append(
            f"{len(report['shared_documentation'])} shared documentation relationship(s)"
        )
    if report["shared_knowledge"]:
        summary_parts.append(f"{len(report['shared_knowledge'])} shared knowledge relationship(s)")

    return [
        {
            "type": "Impact",
            "id": f"impact-{matched_context['id']}",
            "title": f"Impact of changing {matched_context['display_name']}: {report['overall_risk']} risk",
            "project": matched_context.get("display_name"),
            "project_id": matched_context.get("id"),
            "item_id": matched_context.get("item_id"),
            "summary": "; ".join(summary_parts),
            "date": report["generated_at"],
            "origin": "Impact Analysis",
            "evidence": report["evidence"][:5],
            "actions": [
                {
                    "label": "Open Project",
                    **_project_nav(matched_context.get("item_id"), matched_context.get("id")),
                }
            ],
            "_title_exact": False,
            "_is_canonical": True,
            "_health_score": matched_context.get("health_score") or 0,
            "_business_value": matched_context.get("business_value"),
        }
    ]


_EXECUTIVE_DECISION_KEYWORDS = ("today", "decision", "recommend", "priority", "focus", "next")


def _search_executive_decision(
    query: str,
    contexts: list[dict[str, Any]],
    enriched_items: list[dict[str, Any]],
    settings: Settings,
) -> list[dict[str, Any]]:
    """Sprint C10: searching "today"/"decision"/"recommend"/"priority"/
    "focus"/"next", or the recommended project's own name, surfaces the
    Executive Decision Engine's current top pick as one searchable card.
    Computed once per search request, reusing the already-fetched
    `contexts`/`enriched_items` -- `search()` doesn't otherwise call the
    full Operational Intelligence/Project Ecosystem engines, so this is a
    genuinely new (not duplicated) pass, gated behind a non-empty query
    the same way `_search_ecosystem`/`_search_impact` already are."""
    from app.executive_decision import get_executive_decision

    query_lower = query.strip().lower()
    if not query_lower:
        return []

    result = get_executive_decision(
        settings=settings, all_contexts=contexts, enriched_items=enriched_items
    )
    decision = result["decision"]
    project = decision.get("recommended_project")
    if project is None:
        return []

    project_name_matches = query_lower in (project.get("display_name") or "").lower()
    keyword_matches = any(k in query_lower for k in _EXECUTIVE_DECISION_KEYWORDS)
    if not (project_name_matches or keyword_matches):
        return []

    return [
        {
            "type": "Executive Decision",
            "id": "executive-decision-today",
            "title": f"Today's Decision: {project['display_name']} ({decision['decision_score']} pts)",
            "project": project.get("display_name"),
            "project_id": project.get("canonical_project_id"),
            "item_id": project.get("item_id"),
            "summary": decision["reason"],
            "date": decision["generated_at"],
            "origin": "Executive Decision Engine",
            "evidence": decision["evidence"][:5],
            "actions": [
                {
                    "label": "Open Project",
                    **_project_nav(project.get("item_id"), project.get("canonical_project_id")),
                }
            ],
            "_title_exact": False,
            "_is_canonical": True,
            "_health_score": 0,
            "_business_value": None,
        }
    ]


_PRIORITY_BONUS = {"critical": 8, "high": 5, "medium": 2, "low": 0}


def _score(result: dict[str, Any], query: str) -> float:
    """Explainable ranking: exact match > canonical project > title/
    filename/summary substring matches > recent activity > ProjectContext
    priority. Every term below is a plain, documented number, not a
    hidden/learned weight."""
    score = 0.0
    title = (result.get("title") or "").lower()
    summary = (result.get("summary") or "").lower()
    q = query.lower()

    if result.get("_title_exact"):
        score += 100
    elif q and q in title:
        score += 40
    if result.get("_filename_match"):
        score += 30
    if q and q in summary:
        score += 10
    if result.get("_is_canonical"):
        score += 15

    date = result.get("date")
    if date:
        # Cheap, dependency-free recency bonus: newer ISO date strings sort
        # (and therefore score) higher purely by string comparison over a
        # fixed recent window -- no datetime parsing needed since ISO 8601
        # strings already sort chronologically.
        score += 5 if date > "2020-01-01" else 0
        score += 3 if date > "2026-01-01" else 0

    score += (result.get("_health_score") or 0) / 20.0  # 0-5 points
    score += _PRIORITY_BONUS.get(result.get("_business_value"), 0)

    return score


def _strip_internal_fields(result: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in result.items() if not k.startswith("_")}


def search(
    query: str = "",
    *,
    types: list[str] | None = None,
    limit_per_type: int = _DEFAULT_LIMIT_PER_TYPE,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """The one Explorer 2.0 search entry point. Empty `query` returns
    everything (bounded by `limit_per_type`) rather than nothing -- useful
    for an initial "browse" load. `types` restricts to a subset of
    `RESULT_TYPES` (the Filters row); omitted, every domain is searched."""
    from app.assets.service import request_scope

    settings = settings or get_settings()
    contexts, enriched_items = _all_project_contexts(settings)

    all_results: list[dict[str, Any]] = []
    with request_scope():
        all_results += _search_projects(query, contexts)
        sessions, snapshots = _search_ai_sessions_and_snapshots(query, contexts, settings)
        all_results += sessions
        all_results += snapshots
        all_results += _search_commits(query, contexts)
        all_results += _search_timeline_events(query, contexts, settings)
        all_results += _search_markdown(query, contexts)
        all_results += _search_assets(query, contexts, settings)
        all_results += _search_knowledge(query, settings)
        all_results += _search_conversations(query, settings)
        all_results += _search_decisions(query, contexts, settings)
        caps, deps = _search_capabilities_and_dependencies(query, contexts, settings)
        all_results += caps
        all_results += deps
        all_results += _search_recommendations(query, contexts, enriched_items, settings)
        # Sprint C8/C9: shares the same `request_scope()` -- the shared-
        # assets detector reuses the exact walk `_search_assets` above
        # already did, never a second one. Relationships are computed once
        # here and passed to both `_search_ecosystem` and `_search_impact`
        # (Sprint C9) so the Project Ecosystem Engine's detector registry
        # never runs twice for one search request.
        if query.strip():
            from app.project_ecosystem import compute_relationships

            relationships = compute_relationships(all_contexts=contexts, settings=settings)
            all_results += _search_ecosystem(query, contexts, settings, relationships=relationships)
            all_results += _search_impact(query, contexts, settings, relationships=relationships)
            all_results += _search_executive_decision(query, contexts, enriched_items, settings)

    if types:
        wanted = set(types)
        all_results = [r for r in all_results if r["type"] in wanted]

    for r in all_results:
        r["_score"] = _score(r, query)
    all_results.sort(key=lambda r: (-r["_score"], r["type"], (r.get("title") or "").lower()))

    groups: dict[str, list[dict[str, Any]]] = {t: [] for t in RESULT_TYPES}
    for r in all_results:
        if len(groups[r["type"]]) < limit_per_type:
            groups[r["type"]].append(_strip_internal_fields(r))

    counts = {t: len(groups[t]) for t in RESULT_TYPES}
    total = sum(counts.values())

    return {"query": query, "total": total, "counts": counts, "groups": groups}


def project_hub(project_id: str, settings: Settings | None = None) -> dict[str, Any] | None:
    """Project Hub: everything about one project, composed entirely from
    existing services -- `ProjectContext` for Overview, `app.projects.db`
    for Sessions/Snapshots, `workspace.service` for Assets/Recent Activity,
    `app.db` for Knowledge (soft name cross-reference, same as
    `ProjectContext.knowledge_count`), and Advisor for Recommendations. No
    new computation, no new storage -- purely a shaped read."""
    from app.assets.service import request_scope
    from app.impact_analysis import get_impact_analysis
    from app.project_context.builder import all_project_contexts, build_project_context
    from app.project_ecosystem import compute_relationships, get_project_ecosystem

    settings = settings or get_settings()

    with request_scope():
        context = build_project_context(project_id=project_id, settings=settings)
        if context is None:
            return None

        sessions = projects_db.list_ai_sessions(project_id, settings=settings)
        snapshots = []
        for s in sessions:
            snapshots.extend(projects_db.list_ai_session_snapshots(s["id"], settings=settings))
        snapshots.sort(key=lambda s: s.get("created_at") or "", reverse=True)

        assets: list[dict[str, Any]] = []
        if context.get("root_path"):
            try:
                assets = [
                    assets_index.asset_record_to_dict(r)
                    for r in assets_index.index_assets_for_project(
                        context["root_path"],
                        context["display_name"],
                        canonical_project_id=context["id"],
                        discovery_item_id=context.get("item_id"),
                    )
                ]
            except OSError:
                assets = []

        # Sprint C8: Project Ecosystem -- relationships to other projects,
        # from the same canonical Assets/Knowledge/PI-dependencies evidence
        # already read above/elsewhere, wrapped in the same `request_scope()`
        # so its own whole-workspace asset walk never repeats this
        # project's asset walk above. Sprint C9: `all_contexts`/
        # `relationships` are computed once here and threaded into both
        # `get_project_ecosystem` and `get_impact_analysis` -- the latter
        # never repeats the Ecosystem Engine's own detector pass.
        all_contexts, enriched_items_for_ecosystem = all_project_contexts(settings=settings)
        relationships = compute_relationships(all_contexts=all_contexts, settings=settings)
        ecosystem = get_project_ecosystem(
            project_id, settings=settings, all_contexts=all_contexts, relationships=relationships
        )
        impact = get_impact_analysis(
            project_id,
            settings=settings,
            all_contexts=all_contexts,
            enriched_items=enriched_items_for_ecosystem,
            relationships=relationships,
        )

    # Sprint C4 §9 (Project Integration): asset/reusable counts and a
    # category breakdown, all derived from the same canonical `assets`
    # list above -- never a second computation of "how many assets".
    assets_summary = {
        "count": len(assets),
        "reusable_count": sum(1 for a in assets if a["reusable"]),
        "by_category": {
            cat: sum(1 for a in assets if a["category"] == cat)
            for cat in sorted({a["category"] for a in assets})
        },
    }

    recent_activity = context.get("recent_activity") or []
    timeline = context.get("timeline") or []
    recommendations = context.get("advisor_summary") or []

    try:
        knowledge = [
            row
            for row in knowledge_db.list_projects(settings=settings)
            if (row["project"] or "").strip().lower() == context["display_name"].strip().lower()
        ]
    except Exception:
        knowledge = []

    return {
        "overview": context,
        "sessions": sessions,
        "snapshots": snapshots,
        "assets": assets,
        "assets_summary": assets_summary,
        "knowledge": knowledge,
        "recent_activity": recent_activity,
        "commits": context.get("commits") or [],
        "timeline": timeline,
        "recommendations": recommendations,
        "ecosystem": ecosystem,
        "impact_analysis": impact,
    }
