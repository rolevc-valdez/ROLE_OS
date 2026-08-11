"""Unified Recent Activity feed (Sprint 4 §7).

Merges events from every source Workspace Adoption already knows about --
git commits, filesystem modification times, adoption/ignore/override
state changes, AI Sessions/Snapshots, and discovered assets -- into one
time-sorted, deduplicated list. Pure aggregation over data other modules
already computed; this file performs no filesystem or git access of its
own.
"""

from __future__ import annotations

from typing import Any


def _event(
    event_type: str, timestamp: str | None, project_id: str, project_name: str, summary: str
) -> dict[str, Any] | None:
    if not timestamp:
        return None
    return {
        "type": event_type,
        "timestamp": timestamp,
        "project_id": project_id,
        "project_name": project_name,
        "summary": summary,
    }


def build_activity_feed(
    enriched_items: list[dict[str, Any]],
    *,
    assets_by_project: dict[str, list[dict[str, Any]]] | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """`enriched_items` = `service.list_enriched_top_level_projects()`'s
    output (each already carries `discovery_detail`, `ai_sessions`,
    overlay timestamps). `assets_by_project` is optional: {item_id:
    [AssetRecord dicts]} from `assets_index`, if the caller already
    fetched it (avoids re-walking the filesystem here)."""
    assets_by_project = assets_by_project or {}
    events: list[dict[str, Any]] = []
    seen: set[tuple] = set()

    def add(event: dict[str, Any] | None) -> None:
        if event is None:
            return
        key = (event["type"], event["timestamp"], event["project_id"])
        if key in seen:
            return
        seen.add(key)
        events.append(event)

    for item in enriched_items:
        project_id = item["id"]
        project_name = item["name"]
        detail = item.get("discovery_detail") or {}
        git = detail.get("git") or {}

        for commit in git.get("recent_commits") or []:
            add(
                _event(
                    "git_commit",
                    commit.get("date"),
                    project_id,
                    project_name,
                    commit.get("message", ""),
                )
            )

        add(
            _event(
                "filesystem_modified",
                item.get("last_modified"),
                project_id,
                project_name,
                f"Files changed in {project_name}",
            )
        )

        if item.get("adopted_at"):
            add(
                _event(
                    "adopted",
                    item["adopted_at"],
                    project_id,
                    project_name,
                    f"{project_name} adopted into Workspace",
                )
            )

        ai_sessions = item.get("ai_sessions") or {}
        for session in ai_sessions.get("sessions") or []:
            add(
                _event(
                    "ai_session",
                    session.get("last_used_at") or session.get("started_at"),
                    project_id,
                    project_name,
                    f"AI session ({session.get('assistant', 'unknown')}): {session.get('title') or 'untitled'}",
                )
            )
        latest_snapshot = ai_sessions.get("latest_snapshot")
        if latest_snapshot:
            add(
                _event(
                    "ai_snapshot",
                    latest_snapshot.get("created_at"),
                    project_id,
                    project_name,
                    latest_snapshot.get("summary") or "Session snapshot recorded",
                )
            )

        for asset in assets_by_project.get(project_id, []):
            add(
                _event(
                    "asset_discovered",
                    asset.get("modified_at"),
                    project_id,
                    project_name,
                    f"Asset: {asset.get('filename')}",
                )
            )

    events.sort(key=lambda e: e["timestamp"], reverse=True)
    return events[:limit]
