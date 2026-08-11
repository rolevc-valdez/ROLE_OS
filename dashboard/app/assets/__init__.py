"""Assets OS (Sprint C4): the canonical asset domain -- indexing,
classification, duplicate grouping, safe previews, and user overrides
(reusable/category/favorite) over real files discovered under adopted
project roots. See `service.py`'s module docstring for the full
architecture.
"""

from __future__ import annotations

from app.assets.model import AssetRecord, asset_record_to_dict, compute_asset_id
from app.assets.service import (
    find_duplicates,
    get_asset,
    get_duplicate_group,
    index_project_assets,
    list_all_assets,
    search_assets,
)

__all__ = [
    "AssetRecord",
    "asset_record_to_dict",
    "compute_asset_id",
    "find_duplicates",
    "get_asset",
    "get_duplicate_group",
    "index_project_assets",
    "list_all_assets",
    "search_assets",
]
