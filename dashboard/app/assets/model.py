"""The canonical AssetRecord (Sprint C4: Assets OS).

One shape, used by the Assets gallery, Explorer's Asset result type,
Project Detail/Project Hub, Dashboard previews, and (per the brief) future
Mission Control work. Project identity is never duplicated onto this
record beyond the two id fields (`canonical_project_id`/
`discovery_item_id`) -- everything else about "which project" (name,
health, workspace, ...) is resolved through `ProjectContext`/canonical
identity by whoever renders this record, never re-derived here.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field


def compute_asset_id(absolute_path: str) -> str:
    """Deterministic, stable across rescans as long as the file doesn't
    move -- the same `sha1(path)` identity convention
    `app.discovery.identity.compute_item_id` already uses for Workspace
    items."""
    return hashlib.sha1(absolute_path.encode("utf-8")).hexdigest()[:16]


@dataclass
class AssetRecord:
    asset_id: str
    canonical_project_id: str | None
    discovery_item_id: str | None
    filename: str
    absolute_path: str
    relative_path: str
    extension: str
    asset_type: str
    category: str
    mime_type: str
    size_bytes: int
    modified_at: str
    reusable: bool
    likely_logo: bool
    duplicate_hash: str | None
    duplicate_group_id: str | None
    preview_available: bool
    preview_url: str | None
    source: str
    width: int | None = None
    height: int | None = None
    duration_seconds: float | None = None
    favorite: bool = False

    # Backward-compat aliases (Sprint 4's `AssetRecord` -- see
    # `app.workspace.assets_index`'s compatibility shim): every caller
    # that read `.path`/`.project` off the old shape keeps working.
    project: str = ""
    path: str = field(default="", repr=False)

    def __post_init__(self) -> None:
        if not self.path:
            self.path = self.absolute_path


def asset_record_to_dict(record: AssetRecord) -> dict:
    return asdict(record)
