"""Assets OS API (Sprint C4) -- namespaced under `/assets`. The canonical
surface for the Assets gallery, the Asset Detail panel, and Explorer's
Asset results. `GET /workspace/assets` (Sprint 4) is unchanged and keeps
working -- it already delegates to this same canonical index via
`app.workspace.assets_index`'s compatibility shim (Sprint C4).

Every path-touching endpoint below resolves its target exclusively through
`app.assets.service.resolve_safe_path`, which re-derives the real
filesystem path from a validated `asset_id` already present in the live
index and checks it resolves inside a currently-adopted project root --
a client can never submit an arbitrary filesystem path directly (§12).
"""

from __future__ import annotations

import os
import platform
import subprocess
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.assets import db as assets_db
from app.assets import service as assets_service
from app.assets.model import asset_record_to_dict
from app.assets.preview import PreviewError, get_or_create_thumbnail
from app.assets.service import AssetPathError
from app.workspace.service import get_freshness

router = APIRouter(prefix="/assets", tags=["assets"])


def _to_dict(record) -> dict[str, Any]:
    d = asset_record_to_dict(record)
    d.pop("path", None)  # internal back-compat alias only -- not part of the public API shape
    return d


@router.get("")
def list_assets(
    q: str = Query("", description="Search filename/category/project/extension/path"),
    project_id: str | None = Query(None),
    category: str | None = Query(None),
    asset_type: str | None = Query(None),
    extension: str | None = Query(None),
    reusable_only: bool = Query(False),
    favorites_only: bool = Query(False),
    duplicates_only: bool = Query(False),
    sort: str = Query("modified_at"),
    sort_dir: str = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(60, ge=1, le=200),
) -> dict[str, Any]:
    result = assets_service.search_assets(
        query=q,
        project_id=project_id,
        category=category,
        asset_type=asset_type,
        extension=extension,
        reusable_only=reusable_only,
        favorites_only=favorites_only,
        duplicates_only=duplicates_only,
        sort=sort,
        sort_dir=sort_dir,
        page=page,
        page_size=page_size,
    )
    return {**result, "items": [_to_dict(r) for r in result["items"]]}


@router.get("/freshness")
def assets_freshness() -> dict[str, Any]:
    """Reuses `workspace.service.get_freshness()` (Sprint 4 §8) -- the same
    last-scan/staleness signal every other screen already surfaces, not a
    second freshness concept for Assets specifically."""
    return get_freshness()


@router.get("/duplicates/{group_id}")
def duplicate_group(group_id: str) -> dict[str, Any]:
    members = assets_service.get_duplicate_group(group_id)
    if not members:
        raise HTTPException(status_code=404, detail="no duplicate group found for this id")
    return {
        "group_id": group_id,
        "count": len(members),
        "members": [_to_dict(r) for r in members],
    }


@router.get("/{asset_id}")
def get_asset(asset_id: str) -> dict[str, Any]:
    record = assets_service.get_asset(asset_id)
    if record is None:
        raise HTTPException(status_code=404, detail="asset not found")
    body = _to_dict(record)
    if record.duplicate_group_id:
        group = assets_service.get_duplicate_group(record.duplicate_group_id)
        body["duplicate_members"] = [_to_dict(r) for r in group if r.asset_id != asset_id]
    else:
        body["duplicate_members"] = []
    return body


@router.get("/{asset_id}/preview")
def asset_preview(asset_id: str):
    """A resized (max 480px), cached PNG thumbnail for raster images.
    Never serves an original file above the preview size cap, and never
    opens anything outside an adopted project root -- see
    `resolve_safe_path`."""
    try:
        path = assets_service.resolve_safe_path(asset_id)
    except AssetPathError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if path.suffix.lower() == ".svg":
        # Sprint C4 §2: served as its own file with an image/svg+xml type
        # -- safe to embed via <img src=...> (browsers never execute
        # embedded <script> for an image-context SVG), no rasterization
        # needed, no sanitizer dependency.
        return FileResponse(path, media_type="image/svg+xml")

    try:
        thumb_path = get_or_create_thumbnail(asset_id, path)
    except PreviewError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return FileResponse(
        thumb_path, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"}
    )


@router.get("/{asset_id}/file")
def asset_file(asset_id: str):
    """The original file, streamed as-is (never loaded fully into memory
    -- `FileResponse` streams from disk) -- used for native `<video>`/
    `<audio>` playback and direct download. Same path-safety guarantee as
    `/preview`."""
    try:
        path = assets_service.resolve_safe_path(asset_id)
    except AssetPathError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    record = assets_service.get_asset(asset_id)
    return FileResponse(path, media_type=record.mime_type if record else None, filename=path.name)


class OverridePatch(BaseModel):
    reusable: bool | None = None
    category: str | None = None
    favorite: bool | None = None


@router.patch("/{asset_id}")
def patch_asset_override(asset_id: str, payload: OverridePatch) -> dict[str, Any]:
    """User overrides only -- never touches the source file. `reusable`/
    `category`/`favorite` are the only three fields a user can set; every
    other field on an AssetRecord is always derived fresh from the
    filesystem + deterministic classification rules."""
    if assets_service.get_asset(asset_id) is None:
        raise HTTPException(status_code=404, detail="asset not found")
    patch = payload.model_dump(exclude_unset=True)
    assets_db.set_override(asset_id, **patch)
    record = assets_service.get_asset(asset_id)
    return _to_dict(record)


def _confirm_windows() -> None:
    if platform.system() != "Windows":
        raise HTTPException(
            status_code=501,
            detail="Open File/Open Folder are only implemented for the Windows desktop this dashboard normally runs on",
        )


@router.post("/{asset_id}/open-file")
def open_file(asset_id: str) -> dict[str, Any]:
    """Opens the asset in its OS-default application, on the same machine
    the dashboard server is running on -- appropriate for a localhost-only,
    single-user personal tool (never proxies to a remote client). Never
    copies, moves, renames, edits, or deletes anything."""
    _confirm_windows()
    try:
        path = assets_service.resolve_safe_path(asset_id)
    except AssetPathError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        os.startfile(str(path))  # noqa: S606 -- Windows-only, path already validated above
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"could not open file: {exc}") from exc
    return {"opened": str(path)}


@router.post("/{asset_id}/open-folder")
def open_folder(asset_id: str) -> dict[str, Any]:
    """Opens the asset's containing folder in File Explorer with the file
    pre-selected. Same safety/scope guarantees as `open_file`."""
    _confirm_windows()
    try:
        path = assets_service.resolve_safe_path(asset_id)
    except AssetPathError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        subprocess.run(["explorer", "/select,", str(path)], check=False)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"could not open folder: {exc}") from exc
    return {"opened_folder": str(path.parent)}
