"""Settings API (Sprint 8), namespaced under /settings.

Centralizes configuration and metadata that already exists elsewhere in
the app -- database paths (from `Settings`, env-var driven, unchanged),
live counts (from the imports/extraction domains), graph status (from the
Sprint 5 Knowledge Graph engine), and version/commit/license info. No new
persistence model: everything here is either read from an environment
variable, computed from an existing database on read, or read from the
filesystem/git at request time.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.conversation_graph.engine import build_graph
from app.extraction import db as extraction_db
from app.imports import db as imports_db

router = APIRouter(prefix="/settings", tags=["settings"])

# Maps each exported/importable config field to the environment variable
# that actually controls it, so "Import configuration" can tell the user
# exactly what to set -- this app has no mechanism (and, per this
# sprint's scope, should not grow one) to mutate a running process's
# environment, so importing can only validate and preview, never apply.
_ENV_VAR_MAP = {
    "db_path": "ROLE_OS_DB_PATH",
    "projects_db_path": "ROLE_OS_PROJECTS_DB_PATH",
    "advisor_db_path": "ROLE_OS_ADVISOR_DB_PATH",
    "imports_db_path": "ROLE_OS_IMPORTS_DB_PATH",
    "extraction_db_path": "ROLE_OS_EXTRACTION_DB_PATH",
    "default_import_path": "ROLE_OS_DEFAULT_IMPORT_PATH",
    "search_result_limit": "ROLE_OS_SEARCH_RESULT_LIMIT",
}


class GeneralSettings(BaseModel):
    app_name: str
    app_version: str
    database_paths: dict[str, str]
    default_import_path: str | None
    search_result_limit: int


class SystemStatus(BaseModel):
    total_conversations: int
    total_extracted_objects: int
    database_location: str
    database_sizes_bytes: dict[str, int | None]
    last_import: str | None
    last_extraction: str | None


class AboutInfo(BaseModel):
    version: str
    commit: str | None
    build_date: str | None
    license: str


class MaintenanceStatus(BaseModel):
    cache_exists: bool
    cache_description: str


class SettingsOverview(BaseModel):
    general: GeneralSettings
    system: SystemStatus
    about: AboutInfo
    maintenance: MaintenanceStatus


class RebuildGraphResult(BaseModel):
    nodes: int
    edges: int
    rebuilt_at: str


class ClearCacheResult(BaseModel):
    cleared: bool
    cache: str


class ImportPreview(BaseModel):
    valid: bool
    parsed: dict[str, Any]
    env_vars_to_set: dict[str, Any]
    note: str


def _database_paths(settings: Settings) -> dict[str, str]:
    return {
        "builder": str(settings.db_path),
        "projects": str(settings.projects_db_path),
        "advisor": str(settings.advisor_db_path),
        "imports": str(settings.imports_db_path),
        "extraction": str(settings.extraction_db_path),
    }


def _database_sizes(settings: Settings) -> dict[str, int | None]:
    sizes: dict[str, int | None] = {}
    for name, path_str in _database_paths(settings).items():
        path = Path(path_str)
        sizes[name] = path.stat().st_size if path.exists() else None
    return sizes


def _git_commit(settings: Settings) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=settings.repo_root,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        return result.stdout.strip() or None
    except Exception:
        return None  # not a git checkout, git unavailable, or any other lookup failure


def _general(settings: Settings) -> GeneralSettings:
    return GeneralSettings(
        app_name=settings.app_name,
        app_version=settings.app_version,
        database_paths=_database_paths(settings),
        default_import_path=settings.default_import_path or None,
        search_result_limit=settings.search_result_limit,
    )


def _system(settings: Settings) -> SystemStatus:
    counts = extraction_db.counts_by_type(settings=settings)
    last_import_runs = imports_db.list_runs(settings=settings, limit=1)
    last_extraction_runs = extraction_db.list_recent_runs(limit=1, settings=settings)
    return SystemStatus(
        total_conversations=imports_db.count_conversations(settings=settings),
        total_extracted_objects=sum(counts.values()),
        database_location=str(settings.imports_db_path.parent),
        database_sizes_bytes=_database_sizes(settings),
        last_import=last_import_runs[0]["completed_at"] if last_import_runs else None,
        last_extraction=last_extraction_runs[0]["completed_at"] if last_extraction_runs else None,
    )


def _about(settings: Settings) -> AboutInfo:
    return AboutInfo(
        version=settings.app_version,
        commit=_git_commit(settings),
        build_date=None,  # no build pipeline stamps one; reported honestly rather than faked
        license=settings.license,
    )


def _maintenance() -> MaintenanceStatus:
    # The one real, clearable cache in this process: get_settings()'s
    # @lru_cache memoization. Clearing it lets an updated environment
    # variable take effect on the next request without a full restart.
    return MaintenanceStatus(
        cache_exists=True,
        cache_description="In-memory Settings cache (get_settings())",
    )


@router.get("", response_model=SettingsOverview)
def get_settings_overview(settings: Settings = Depends(get_settings)) -> SettingsOverview:
    return SettingsOverview(
        general=_general(settings),
        system=_system(settings),
        about=_about(settings),
        maintenance=_maintenance(),
    )


@router.get("/export")
def export_settings(settings: Settings = Depends(get_settings)):
    from fastapi.responses import Response

    payload = {
        "general": _general(settings).model_dump(),
        "about": _about(settings).model_dump(),
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    return Response(
        content=body,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="role_os_settings.json"'},
    )


@router.post("/import", response_model=ImportPreview)
async def import_settings(file: UploadFile = File(...)) -> ImportPreview:
    """Validates an uploaded configuration JSON file and previews what it
    contains. Does not, and cannot safely, apply it to the running
    process -- there is no mechanism (and this sprint adds none) to
    mutate a live server's environment variables. The response tells the
    caller exactly which environment variable to set for each recognized
    field so they can apply it themselves and restart.
    """
    raw = await file.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"File is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Expected a JSON object at the top level")

    general = data.get("general", data)  # accept either the full export shape or a flat object
    if not isinstance(general, dict):
        raise HTTPException(status_code=400, detail="'general' must be a JSON object")

    env_vars: dict[str, Any] = {}
    for field, env_var in _ENV_VAR_MAP.items():
        if field in general:
            env_vars[env_var] = general[field]
        elif field == "default_import_path" and "default_import_path" in general:
            env_vars[env_var] = general["default_import_path"]

    database_paths = general.get("database_paths")
    if isinstance(database_paths, dict):
        name_to_field = {"builder": "db_path", "projects": "projects_db_path", "advisor": "advisor_db_path",
                          "imports": "imports_db_path", "extraction": "extraction_db_path"}
        for name, value in database_paths.items():
            field = name_to_field.get(name)
            if field:
                env_vars[_ENV_VAR_MAP[field]] = value

    return ImportPreview(
        valid=True,
        parsed=general,
        env_vars_to_set=env_vars,
        note="Configuration validated. ROLE OS does not apply settings to a running "
        "server automatically -- set these environment variables and restart to apply them.",
    )


@router.post("/maintenance/rebuild-graph", response_model=RebuildGraphResult)
def rebuild_graph(settings: Settings = Depends(get_settings)) -> RebuildGraphResult:
    """The Knowledge Graph (Sprint 5) is always computed fresh on every
    request -- there is nothing to invalidate. This action exists to give
    "Rebuild" concrete, honest meaning: it forces a fresh build right now
    and reports what it found, rather than pretending to warm a cache
    that doesn't exist."""
    graph = build_graph(settings)
    return RebuildGraphResult(
        nodes=len(graph.nodes),
        edges=len(graph.edges),
        rebuilt_at=datetime.now(timezone.utc).isoformat(),
    )


@router.post("/maintenance/clear-cache", response_model=ClearCacheResult)
def clear_cache() -> ClearCacheResult:
    get_settings.cache_clear()
    return ClearCacheResult(cleared=True, cache="settings")
