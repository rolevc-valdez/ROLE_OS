"""Explicit Project Registration (Role OS 2.0, Phase 3 Task 4).

Lets Role intentionally point Role OS at one isolated project folder (e.g.
`C:\\Users\\rolev\\bolsa-de-trabajo`) by path, without widening any
Discovery root. The three concepts stay separate:

- **Discovery** -- `app.discovery` scanning configured roots (unchanged).
- **Registration** (this module) -- Role says "this exact folder is a
  project". Only that folder is analyzed, with the same read-only detectors
  and git reader Discovery uses; its parent is never listed or scanned.
- **Adoption** -- the existing `adopted_projects` overlay
  (`service.adopt_item`). Registering never adopts, never classifies, and
  never makes the folder show up in Mission Control; a registered folder
  becomes an ordinary *discovered, not adopted* Workspace item that Role
  can review and adopt through the existing flow.

A registered folder's Discovery analysis is cached in
`registered_projects.snapshot_json` (the same shape the root scan cache
holds) and refreshed on every rescan, so it survives restarts and
Discovery refreshes without depending on `ROLE_OS_DISCOVERY_ROOTS`.
"""

from __future__ import annotations

import dataclasses
import os
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings
from app.discovery.boundary import assign_boundaries
from app.discovery.classifier import classify
from app.discovery.detectors import analyze_folder
from app.discovery.git_reader import read_git_info
from app.discovery.identity import compute_item_id
from app.workspace import db

REGISTRATION_SOURCE_EXPLICIT = "explicit"
REGISTRATION_SOURCE_DISCOVERY = "discovery"

# Reported (never parsed) when present at the folder's top level -- P3.5
# owns ROLE_PROJECT.md ingestion.
_REPORTED_MANIFEST_FILES = ("ROLE_PROJECT.md", "README.md")


class RegistrationError(ValueError):
    """A path that cannot be registered, with a stable machine-readable
    `code` (`empty`, `not_absolute`, `not_found`, `not_directory`,
    `inaccessible`, `too_broad`, `already_registered`,
    `already_discovered`, `not_registered`, `has_workspace_data`)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def path_key(path: str | Path) -> str:
    """Comparison key: Windows drive/letter casing and trailing separators
    are equal (same rule as `app.discovery.roots._normalize_key`)."""
    return os.path.normcase(os.path.normpath(str(path)))


def _is_same_or_ancestor(candidate_key: str, other_key: str) -> bool:
    prefix = candidate_key.rstrip("\\/") + os.sep
    return other_key == candidate_key or other_key.startswith(prefix)


def normalize_path(raw: str | None) -> Path:
    """Validates a user-entered folder path and returns its resolved,
    real-cased absolute form. Read-only: stat/scandir only. Raises
    `RegistrationError` for anything that is not a safe, single project
    folder."""
    text = (raw or "").strip().strip('"').strip("'").strip()
    if not text:
        raise RegistrationError("empty", "Enter a project folder path.")
    candidate = Path(text)
    if not candidate.is_absolute():
        raise RegistrationError(
            "not_absolute", f"Use a full folder path (for example C:\\Users\\you\\project), not '{text}'."
        )
    try:
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError:
        raise RegistrationError("not_found", f"Folder does not exist: {text}") from None
    except PermissionError:
        raise RegistrationError("inaccessible", f"Folder cannot be accessed: {text}") from None
    except OSError as exc:
        raise RegistrationError("not_found", f"Folder cannot be resolved: {text} ({exc})") from None

    try:
        is_dir = resolved.is_dir()
    except PermissionError:
        raise RegistrationError("inaccessible", f"Folder cannot be accessed: {resolved}") from None
    if not is_dir:
        raise RegistrationError("not_directory", f"Not a folder: {resolved}")

    try:
        with os.scandir(resolved) as it:
            next(it, None)
    except PermissionError:
        raise RegistrationError("inaccessible", f"Folder cannot be read (permission denied): {resolved}") from None
    except OSError as exc:
        raise RegistrationError("inaccessible", f"Folder cannot be read: {resolved} ({exc})") from None

    key = path_key(resolved)
    if resolved.parent == resolved:
        raise RegistrationError("too_broad", f"A whole drive cannot be registered as one project: {resolved}")
    try:
        home_key = path_key(Path.home().resolve())
    except (OSError, RuntimeError):
        home_key = None
    if home_key and _is_same_or_ancestor(key, home_key):
        raise RegistrationError(
            "too_broad",
            f"{resolved} is your user profile (or contains it) -- register the specific project folder inside it instead.",
        )
    return resolved


def analyze_registered_folder(path: Path) -> dict[str, Any]:
    """Runs the existing, read-only Discovery pipeline on exactly one
    folder -- the same stages `app.discovery.service.run_audit` applies to
    each candidate -- without listing or scanning its parent."""
    project = analyze_folder(path)
    project.depth = 1
    project.parent_path = None
    project.git = read_git_info(path)
    classify(project)
    assign_boundaries([project])
    if not project.is_top_level_project:
        # Role explicitly said "this folder is a project" -- that is the
        # boundary evidence. Discovery's own weaker verdict stays visible.
        project.boundary_evidence = [
            "explicitly registered by Role as a project folder",
            *project.boundary_evidence,
        ]
        project.item_kind = "project"
        project.is_top_level_project = True
        project.parent_item_id = None
        project.project_root_id = project.item_id
        project.hierarchy_depth = 0
    data = dataclasses.asdict(project)
    data["registration_source"] = REGISTRATION_SOURCE_EXPLICIT
    return data


def _discovered_item_for_key(key: str, settings: Settings) -> dict[str, Any] | None:
    cache = db.load_scan_cache(settings)
    for project in (cache["projects"] if cache else []):
        if path_key(project["root_path"]) == key:
            return project
    return None


def _containing_project_name(key: str, settings: Settings) -> str | None:
    """A known (discovered or registered) project that already contains
    this folder -- reported as a warning, never used to widen anything."""
    cache = db.load_scan_cache(settings)
    known = [
        (p["root_path"], p["name"])
        for p in (cache["projects"] if cache else [])
        if p.get("is_top_level_project")
    ]
    known += [(r["root_path"], r["snapshot"].get("name")) for r in db.list_registrations(settings)]
    for root_path, name in known:
        other = path_key(root_path)
        if other != key and key.startswith(other.rstrip("\\/") + os.sep):
            return name
    return None


def _manifests(snapshot: dict[str, Any], path: Path) -> list[str]:
    found: list[str] = []
    for marker in snapshot.get("tech_markers") or []:
        try:
            found.append(Path(marker).relative_to(path).as_posix())
        except ValueError:
            found.append(str(marker))
    for name in _REPORTED_MANIFEST_FILES:
        try:
            if (path / name).is_file() and name not in found:
                found.append(name)
        except OSError:
            continue
    if snapshot.get("operational_manifest"):
        found.append(".role-os/project-status.json")
    return found


def _review(
    snapshot: dict[str, Any],
    *,
    item_id: str,
    registration_status: str,
    settings: Settings,
) -> dict[str, Any]:
    git = snapshot.get("git") or {}
    overlay = db.get_overlay(item_id, settings)
    if overlay and overlay.get("adopted"):
        adoption_status = "adopted"
    elif overlay and overlay.get("ignored"):
        adoption_status = "ignored"
    else:
        adoption_status = "not_adopted"
    path = Path(snapshot["root_path"])
    return {
        "valid": True,
        "error": None,
        "item_id": item_id,
        "name": snapshot.get("name"),
        "path": snapshot["root_path"],
        "is_git_repo": bool(git.get("is_repo")),
        "git_remote": git.get("remote_url"),
        "git_branch": git.get("branch"),
        "git_last_commit_date": git.get("last_commit_date"),
        "git_last_commit_message": git.get("last_commit_message"),
        "classification": snapshot.get("classification"),
        "manifests": _manifests(snapshot, path),
        "has_readme": bool(snapshot.get("has_readme")),
        "canonical_project_id": (overlay or {}).get("canonical_project_id"),
        "registration_status": registration_status,
        "adoption_status": adoption_status,
        "inside_known_project": _containing_project_name(path_key(path), settings),
    }


def _invalid(raw: str | None, exc: RegistrationError) -> dict[str, Any]:
    return {
        "valid": False,
        "error": {"code": exc.code, "message": exc.message},
        "path": (raw or "").strip(),
        "registration_status": "not_registered",
        "adoption_status": "not_adopted",
    }


def inspect_path(raw: str | None, settings: Settings | None = None) -> dict[str, Any]:
    """VALIDATE + INSPECT, read-only: nothing is persisted. Returns a
    review card; `valid: False` with an `error` for an unusable path."""
    settings = settings or get_settings()
    try:
        path = normalize_path(raw)
    except RegistrationError as exc:
        return _invalid(raw, exc)
    key = path_key(path)

    registration = db.get_registration_by_key(key, settings)
    if registration is not None:
        return _review(
            registration["snapshot"], item_id=registration["id"], registration_status="registered", settings=settings
        )
    discovered = _discovered_item_for_key(key, settings)
    if discovered is not None:
        return _review(
            discovered,
            item_id=compute_item_id(discovered["root_path"]),
            registration_status="discovered_via_root",
            settings=settings,
        )
    snapshot = analyze_registered_folder(path)
    return _review(
        snapshot, item_id=compute_item_id(str(path)), registration_status="not_registered", settings=settings
    )


def register_path(raw: str | None, settings: Settings | None = None) -> dict[str, Any]:
    """REGISTER: persists one `registered_projects` row for exactly this
    folder. Never adopts, classifies, or touches the folder itself."""
    settings = settings or get_settings()
    path = normalize_path(raw)
    key = path_key(path)
    existing = db.get_registration_by_key(key, settings)
    if existing is not None:
        raise RegistrationError("already_registered", f"Already registered: {existing['root_path']}")
    discovered = _discovered_item_for_key(key, settings)
    if discovered is not None:
        raise RegistrationError(
            "already_discovered",
            f"{discovered['root_path']} is already found by Discovery -- review/adopt it from the Workspace list instead.",
        )
    snapshot = analyze_registered_folder(path)
    item_id = compute_item_id(str(path))
    db.insert_registration(item_id, str(path), key, snapshot, settings=settings)
    return _review(snapshot, item_id=item_id, registration_status="registered", settings=settings)


def list_registered(settings: Settings | None = None) -> list[dict[str, Any]]:
    settings = settings or get_settings()
    result = []
    for registration in db.list_registrations(settings):
        review = _review(
            registration["snapshot"], item_id=registration["id"], registration_status="registered", settings=settings
        )
        review.update(
            registered_at=registration["registered_at"],
            snapshot_at=registration["snapshot_at"],
            last_error=registration["last_error"],
            source=registration["source"],
        )
        result.append(review)
    return result


def unregister(item_id: str, settings: Settings | None = None) -> dict[str, Any]:
    """Forgets Role OS's registration of a folder. Only the
    `registered_projects` row is deleted -- the folder, its files, and its
    git history are never touched. Blocked while the item is adopted or
    carries Workspace data (canonical project identity, notes), so those
    relationships are never silently orphaned."""
    settings = settings or get_settings()
    registration = db.get_registration(item_id, settings)
    if registration is None:
        raise RegistrationError("not_registered", "No explicit registration with that id.")
    overlay = db.get_overlay(item_id, settings) or {}
    if overlay.get("adopted") or overlay.get("canonical_project_id") or overlay.get("notes"):
        raise RegistrationError(
            "has_workspace_data",
            f"{registration['root_path']} is adopted or has Role OS data attached -- "
            "it cannot be unregistered from here.",
        )
    db.delete_registration(item_id, settings)
    return {"unregistered": True, "item_id": item_id, "path": registration["root_path"]}


def refresh_all(settings: Settings | None = None) -> None:
    """Re-analyzes every registered folder (called by `service.rescan`).
    A folder that has moved/vanished keeps its last snapshot and records
    the error -- registration is never silently dropped."""
    settings = settings or get_settings()
    for registration in db.list_registrations(settings):
        try:
            normalize_path(registration["root_path"])  # still a safe, readable folder?
            # Analyze the registered path string itself, so the item id
            # (derived from `root_path`) never drifts between refreshes.
            snapshot = analyze_registered_folder(Path(registration["root_path"]))
        except (RegistrationError, OSError) as exc:
            db.update_registration_snapshot(
                registration["id"], snapshot=None, error=str(exc), settings=settings
            )
            continue
        db.update_registration_snapshot(registration["id"], snapshot=snapshot, error=None, settings=settings)


def registered_snapshots(settings: Settings | None = None) -> list[dict[str, Any]]:
    settings = settings or get_settings()
    return [r["snapshot"] for r in db.list_registrations(settings)]
