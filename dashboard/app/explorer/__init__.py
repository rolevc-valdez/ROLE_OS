"""Explorer 2.0 (Sprint C3): universal search over every domain ROLE OS
already knows about. See `service.py`'s module docstring for the full
architecture -- this is an aggregation layer only, no new storage.
"""

from __future__ import annotations

from app.explorer.service import project_hub, search

__all__ = ["search", "project_hub"]
