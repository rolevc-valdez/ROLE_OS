"""Assets OS (Sprint C4): the canonical asset index, search, and safety
layer. Everything the Assets gallery, Explorer's Asset results, Project
Detail, and Dashboard previews read comes from this one module -- no
second asset mapper anywhere else in the codebase (see `app.workspace.
assets_index`'s compatibility shim, which now delegates here).

The filesystem remains the single source of truth: this module only ever
reads scanned files (to classify, measure, and hash them) and writes to
its own SQLite cache/overrides tables and, for preview thumbnails, its own
`var/` cache directory -- never to a scanned project folder.
"""

from __future__ import annotations

import contextvars
import hashlib
import mimetypes
import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.assets import classification
from app.assets import db as assets_db
from app.assets.image_meta import read_image_dimensions
from app.assets.model import AssetRecord, compute_asset_id
from app.config import Settings, get_settings
from app.discovery.detectors.constants import IGNORE_DIR_NAMES

_MAX_FILES_PER_PROJECT = 2000

# Sprint C5 (Mission Control §12): one HTTP request routinely calls
# `index_project_assets` for the same project's root several times over --
# once per `ProjectContext` (for `assets_count`), again inside
# `workspace.service.list_project_assets` (for Dashboard/Home/Mission
# Control's recent-assets lists), again inside the activity feed. Each call
# is a full filesystem walk. `request_scope()` lets a top-level request
# handler opt into memoizing that walk by root path for the lifetime of one
# request, without changing any caller's signature or the per-file
# path+mtime+size cache above (which stays -- this is a coarser, request-
# lifetime cache on top of it). Absent a `request_scope()`, behavior is
# unchanged: every call walks the filesystem, exactly as before.
_request_cache: contextvars.ContextVar[dict[tuple[str, int], list[AssetRecord]] | None] = (
    contextvars.ContextVar("_assets_request_cache", default=None)
)


@contextmanager
def request_scope() -> Iterator[None]:
    token = _request_cache.set({})
    try:
        yield
    finally:
        _request_cache.reset(token)


_HASH_BYTES = 1_048_576  # partial-content hash: first 1MB, a practical dedup signal
_MAX_PREVIEW_SOURCE_BYTES = 25_000_000  # never open/serve an original above this for preview

mimetypes.add_type("image/webp", ".webp")
mimetypes.add_type("font/ttf", ".ttf")
mimetypes.add_type("font/otf", ".otf")
mimetypes.add_type("font/woff", ".woff")
mimetypes.add_type("font/woff2", ".woff2")

_PREVIEWABLE_MIME_PREFIXES = ("image/",)
_PREVIEWABLE_EXT = classification.IMAGE_EXT


def _partial_hash(path: Path) -> str | None:
    try:
        h = hashlib.sha1()
        with open(path, "rb") as fh:
            h.update(fh.read(_HASH_BYTES))
        return h.hexdigest()
    except OSError:
        return None


def _build_record(
    *,
    entry_path: Path,
    root: Path,
    project_name: str,
    canonical_project_id: str | None,
    discovery_item_id: str | None,
    size_bytes: int,
    mtime: float,
    overrides: dict[str, dict[str, Any]],
    settings: Settings,
) -> AssetRecord | None:
    name = entry_path.name
    ext = entry_path.suffix.lower()
    if ext not in classification.ASSET_EXT:
        return None

    absolute_path = str(entry_path)
    asset_id = compute_asset_id(absolute_path)

    cached = assets_db.get_cached(asset_id, size_bytes=size_bytes, mtime=mtime, settings=settings)
    if cached is not None:
        width, height, duplicate_hash = cached["width"], cached["height"], cached["duplicate_hash"]
    else:
        width, height = read_image_dimensions(entry_path, ext)
        duplicate_hash = _partial_hash(entry_path) if size_bytes > 0 else None
        assets_db.set_cached(
            asset_id,
            absolute_path=absolute_path,
            size_bytes=size_bytes,
            mtime=mtime,
            width=width,
            height=height,
            duplicate_hash=duplicate_hash,
            settings=settings,
        )

    # Root-relative, not the full absolute path: an absolute path also
    # embeds every ancestor directory outside the scanned project (the
    # Windows username, "My Drive", a parent workspace folder, a pytest
    # tmp dir named after the running test...), any one of which could
    # coincidentally contain a classification keyword and misclassify
    # every file under it. Relative-to-root keeps the signal to folder
    # names the project itself actually created (e.g. a real "Logos/"
    # subfolder), matching what a human skimming the project would use to
    # judge a file's purpose.
    try:
        folder_path = str(entry_path.parent.relative_to(root))
    except ValueError:
        folder_path = entry_path.parent.name
    category = classification.classify_category(
        filename=name, folder_path=folder_path, extension=ext, width=width, height=height
    )
    reusable = classification.is_reusable(category=category, filename=name)
    likely_logo = classification.detect_likely_logo(category=category, filename=name)
    asset_type = _asset_type_for_extension(ext)
    mime_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
    preview_available = ext in _PREVIEWABLE_EXT and size_bytes <= _MAX_PREVIEW_SOURCE_BYTES

    override = overrides.get(asset_id)
    if override:
        if override.get("reusable") is not None:
            reusable = override["reusable"]
        if override.get("category"):
            category = override["category"]
        favorite = override.get("favorite", False)
    else:
        favorite = False

    try:
        # `.as_posix()`: always forward-slash-separated, regardless of
        # platform -- this field is exposed over JSON/the web, and
        # forward slashes are the universal convention there, not this
        # process's native `os.sep`.
        relative_path = entry_path.relative_to(root).as_posix()
    except ValueError:
        relative_path = name

    return AssetRecord(
        asset_id=asset_id,
        canonical_project_id=canonical_project_id,
        discovery_item_id=discovery_item_id,
        filename=name,
        absolute_path=absolute_path,
        relative_path=relative_path,
        extension=ext,
        asset_type=asset_type,
        category=category,
        mime_type=mime_type,
        size_bytes=size_bytes,
        modified_at=datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat(),
        reusable=reusable,
        likely_logo=likely_logo,
        duplicate_hash=duplicate_hash,
        duplicate_group_id=duplicate_hash,  # resolved to a real group only if 2+ share it -- see group_duplicates()
        preview_available=preview_available,
        preview_url=f"/assets/{asset_id}/preview" if preview_available else None,
        source="discovery",
        width=width,
        height=height,
        duration_seconds=None,  # video/audio duration extraction is out of scope this sprint -- honest None, never guessed
        favorite=favorite,
        project=project_name,
    )


def _asset_type_for_extension(ext: str) -> str:
    if ext in classification.IMAGE_EXT:
        return "image"
    if ext in classification.VIDEO_EXT:
        return "video"
    if ext in classification.AUDIO_EXT:
        return "audio"
    if ext in classification.DOCUMENT_EXT:
        return "document"
    if ext in classification.DESIGN_EXT:
        return "design-file"
    if ext in classification.FONT_EXT:
        return "font"
    return "other"


def index_project_assets(
    root_path: str,
    project_name: str,
    *,
    canonical_project_id: str | None = None,
    discovery_item_id: str | None = None,
    max_files: int = _MAX_FILES_PER_PROJECT,
    settings: Settings | None = None,
) -> list[AssetRecord]:
    """Walks one adopted project's `root_path` looking for real asset
    files -- never copies, moves, renames, edits, or deletes anything.
    Dimensions/duplicate-hash are cache-checked per file (path + mtime +
    size) before being recomputed, so an unchanged file is never re-opened
    or re-hashed on a subsequent call."""
    settings = settings or get_settings()
    root = Path(root_path)
    if not root.is_dir():
        return []

    cache = _request_cache.get()
    cache_key = (str(root), max_files) if cache is not None else None
    if cache_key is not None and cache_key in cache:
        return cache[cache_key]

    # Never index ROLE OS's own runtime data directory -- the folder that
    # actually holds the workspace/projects/assets SQLite files and the
    # generated thumbnail cache this very module writes to -- if a scanned
    # project root happens to *contain* this checkout's runtime dir (as
    # "ROLE_OS" itself does), a live run without this exclusion would index
    # its own cached thumbnails as "discovered assets" and re-thumbnail
    # them on every scan.
    #
    # This is deliberately read from `settings.asset_thumbnail_cache_dir`
    # (already resolved by `Settings.__init__`) rather than re-derived as
    # `repo_root / "var"`: every `var/`-relative default in `config.py` is
    # a *relative* path, so it resolves against the process's current
    # working directory at `Settings()` construction time, not against
    # `repo_root`. Launching the server with cwd=`dashboard/` (as the
    # normal `uvicorn app.main:app` workflow does) therefore actually
    # writes to `dashboard/var/role_os_dashboard/...`, not `var/...` at
    # the repo root -- using the real configured path instead of guessing
    # keeps this exclusion correct for *this process's own* runtime dir.
    #
    # That alone isn't enough: a *different* process (a pytest run, a
    # second dashboard instance, anything launched from yet another cwd)
    # can independently resolve the same relative default to a *third*
    # physical location, and this process's index would have no way to
    # know about it from a single resolved path. `role_os_dashboard` is
    # the one literal, never-varying path segment every `var/`-relative
    # default in `config.py` shares regardless of which `var/` parent it
    # resolves under -- excluding by that directory *name*, the same way
    # `.git`/`node_modules` are excluded in `IGNORE_DIR_NAMES`, catches
    # every physical copy structurally instead of chasing one at a time.
    _RUNTIME_DIR_NAME = "role_os_dashboard"
    runtime_dir = settings.asset_thumbnail_cache_dir.parent.resolve()
    overrides = assets_db.list_overrides(settings=settings)
    records: list[AssetRecord] = []
    stack = [root]
    scanned = 0

    while stack and scanned < max_files:
        current = stack.pop()
        try:
            entries = list(os.scandir(current))
        except OSError:
            continue
        for entry in entries:
            if scanned >= max_files:
                break
            try:
                if entry.is_dir(follow_symlinks=False):
                    if entry.name in IGNORE_DIR_NAMES:
                        continue
                    if entry.is_symlink():
                        continue
                    if entry.name == _RUNTIME_DIR_NAME:
                        continue
                    entry_dir = Path(entry.path).resolve()
                    if entry_dir == runtime_dir or _is_within(entry_dir, runtime_dir):
                        continue
                    stack.append(Path(entry.path))
                    continue
                if not entry.is_file(follow_symlinks=False):
                    continue
                if entry.is_symlink():
                    continue  # never follow a symlink/junction into an asset record
            except OSError:
                continue

            scanned += 1
            try:
                stat = entry.stat(follow_symlinks=False)
            except OSError:
                continue

            record = _build_record(
                entry_path=Path(entry.path),
                root=root,
                project_name=project_name,
                canonical_project_id=canonical_project_id,
                discovery_item_id=discovery_item_id,
                size_bytes=stat.st_size,
                mtime=stat.st_mtime,
                overrides=overrides,
                settings=settings,
            )
            if record is not None:
                records.append(record)

    # `_build_record` sets `duplicate_group_id = duplicate_hash`
    # unconditionally (a raw candidate value); `group_duplicates` is what
    # actually resolves that to a real group id or clears it to `None` for
    # a file that doesn't share its hash with anything else. Every direct
    # caller of this function (Dashboard/Home's recent assets,
    # `ProjectContext.assets_count`'s recent-activity block, Project Hub)
    # must see the same resolved value the `/assets` API returns -- not a
    # raw, unresolved one -- so this is applied here rather than left to
    # each caller to remember. (Scoped to this one project's files; a
    # duplicate whose only other copy lives in a *different* project is
    # still resolved correctly by `list_all_assets`, which re-groups
    # across every project's combined records.)
    result = group_duplicates(records)
    if cache_key is not None:
        cache[cache_key] = result
    return result


def group_duplicates(records: list[AssetRecord]) -> list[AssetRecord]:
    """Assigns a real `duplicate_group_id` (the shared `duplicate_hash`
    value) to records that actually share a hash with at least one other
    record (2+); a unique file's `duplicate_group_id` is cleared to
    `None`. Returns a new list (does not mutate the input).

    Sprint C8 fix: this must *positively assign* the group id, not only
    clear it -- `list_all_assets` calls this a second time on records that
    already went through `index_project_assets`'s own (per-project) call
    to this same function. A record whose only duplicate lives in a
    *different* project has exactly one match within its own project's
    call (cleared to `None` there), so a version of this function that
    only ever clears and never (re)sets can never resolve a cross-project
    duplicate -- it would stay `None` forever, contradicting `list_all_
    assets`'s own docstring guarantee that it re-groups across every
    project's combined records."""
    by_hash: dict[str, list[int]] = {}
    for i, r in enumerate(records):
        if r.duplicate_hash:
            by_hash.setdefault(r.duplicate_hash, []).append(i)

    result = list(records)
    for i, r in enumerate(result):
        group = by_hash.get(r.duplicate_hash) if r.duplicate_hash else None
        new_group_id = r.duplicate_hash if group and len(group) >= 2 else None
        if r.duplicate_group_id != new_group_id:
            result[i] = replace(r, duplicate_group_id=new_group_id)
    return result


def find_duplicates(records: list[AssetRecord]) -> dict[str, list[AssetRecord]]:
    """Groups records sharing the same (non-None) duplicate_hash. Only
    hashes with 2+ matches are returned -- same contract Sprint 4's
    original `assets_index.find_duplicates` had."""
    by_hash: dict[str, list[AssetRecord]] = {}
    for r in records:
        if r.duplicate_hash:
            by_hash.setdefault(r.duplicate_hash, []).append(r)
    return {h: recs for h, recs in by_hash.items() if len(recs) > 1}


def list_all_assets(settings: Settings | None = None) -> list[AssetRecord]:
    """Every asset across every tracked project (workspace-adopted +
    manual PI, deduped by discovery link) -- reuses `app.project_context.
    builder.all_project_contexts`, the one shared aggregator Dashboard and
    Explorer already use (Sprint C3.1), so this introduces no second
    "every project" definition."""
    from app.project_context.builder import all_project_contexts

    settings = settings or get_settings()
    contexts, _enriched_items = all_project_contexts(settings=settings)

    all_records: list[AssetRecord] = []
    for ctx in contexts:
        root_path = ctx.get("root_path")
        if not root_path:
            continue
        records = index_project_assets(
            root_path,
            ctx["display_name"],
            canonical_project_id=ctx["id"],
            discovery_item_id=ctx.get("item_id"),
            settings=settings,
        )
        all_records.extend(records)

    return group_duplicates(all_records)


_SORT_KEYS = {
    "modified_at": lambda r: r.modified_at or "",
    "filename": lambda r: r.filename.lower(),
    "size_bytes": lambda r: r.size_bytes,
    "project": lambda r: (r.project or "").lower(),
}


def search_assets(
    *,
    query: str = "",
    project_id: str | None = None,
    category: str | None = None,
    asset_type: str | None = None,
    extension: str | None = None,
    reusable_only: bool = False,
    favorites_only: bool = False,
    duplicates_only: bool = False,
    sort: str = "modified_at",
    sort_dir: str = "desc",
    page: int = 1,
    page_size: int = 60,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Server-side search/filter/sort/paginate over the canonical asset
    index -- the frontend never scans raw filesystem data itself, it only
    ever renders this already-shaped page."""
    settings = settings or get_settings()
    records = list_all_assets(settings=settings)

    q = query.strip().lower()
    if q:
        records = [
            r
            for r in records
            if q in r.filename.lower()
            or q in r.category.lower()
            or q in (r.project or "").lower()
            or q in r.extension.lower()
            or q in r.relative_path.lower()
        ]
    if project_id:
        records = [r for r in records if r.canonical_project_id == project_id]
    if category:
        records = [r for r in records if r.category == category]
    if asset_type:
        records = [r for r in records if r.asset_type == asset_type]
    if extension:
        records = [r for r in records if r.extension == extension.lower()]
    if reusable_only:
        records = [r for r in records if r.reusable]
    if favorites_only:
        records = [r for r in records if r.favorite]
    if duplicates_only:
        records = [r for r in records if r.duplicate_group_id]

    key_fn = _SORT_KEYS.get(sort, _SORT_KEYS["modified_at"])
    records.sort(key=key_fn, reverse=(sort_dir != "asc"))

    total = len(records)
    page = max(1, page)
    page_size = max(1, min(page_size, 200))
    start = (page - 1) * page_size
    page_records = records[start : start + page_size]

    return {
        "items": page_records,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
    }


def get_asset(asset_id: str, settings: Settings | None = None) -> AssetRecord | None:
    settings = settings or get_settings()
    for record in list_all_assets(settings=settings):
        if record.asset_id == asset_id:
            return record
    return None


def get_duplicate_group(group_id: str, settings: Settings | None = None) -> list[AssetRecord]:
    settings = settings or get_settings()
    return [r for r in list_all_assets(settings=settings) if r.duplicate_group_id == group_id]


# ---------------------------------------------------------------------------
# Path safety (§12): every preview/file/open-file/open-folder action must
# validate the target path resolves inside one of the *currently adopted*
# project roots before touching the filesystem. Never trusts a client-
# supplied path directly -- always re-derives it from a validated
# `asset_id` looked up through the canonical index.
# ---------------------------------------------------------------------------


class AssetPathError(ValueError):
    """Raised for any asset whose resolved path fails the adopted-root
    containment check -- path traversal, a symlink escape, or an asset_id
    that no longer resolves to anything in the live index."""


def resolve_safe_path(asset_id: str, settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    record = get_asset(asset_id, settings=settings)
    if record is None:
        raise AssetPathError(f"no asset found for id '{asset_id}'")

    resolved = Path(record.absolute_path).resolve()
    if not resolved.is_file():
        raise AssetPathError("source file no longer exists")

    from app.project_context.builder import all_project_contexts

    contexts, _ = all_project_contexts(settings=settings)
    adopted_roots = [Path(c["root_path"]).resolve() for c in contexts if c.get("root_path")]
    if not any(_is_within(resolved, root) for root in adopted_roots):
        raise AssetPathError("resolved path is outside every adopted project root")

    return resolved


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
