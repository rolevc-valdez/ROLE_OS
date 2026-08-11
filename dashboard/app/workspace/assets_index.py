"""Compatibility shim over Assets OS (Sprint C4).

Sprint 4 introduced this module as the original read-only asset discovery
index. Sprint C4 (Assets OS) replaced its guts with a real canonical asset
domain (`app.assets`) -- richer records (dimensions, MIME type, duplicate
groups, user overrides, safe preview URLs), a real path+mtime+size cache,
and deterministic category/reusable classification. Every symbol below is
re-exported unchanged so existing callers (`app.workspace.service`,
`app.project_context.builder`, `app.dashboard.service`,
`app.explorer.service`) keep working without modification -- this is the
"delegate legacy endpoints to the canonical service" rule (Sprint C4 §13)
applied at the module level, not just the HTTP layer. There is no second
asset mapper: this file contains no indexing/classification logic of its
own anymore.
"""

from __future__ import annotations

from app.assets.model import AssetRecord, asset_record_to_dict
from app.assets.service import find_duplicates
from app.assets.service import index_project_assets as index_assets_for_project

__all__ = ["AssetRecord", "asset_record_to_dict", "find_duplicates", "index_assets_for_project"]
