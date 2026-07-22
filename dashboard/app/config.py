"""Application configuration.

All settings are read from environment variables so the dashboard can be
pointed at any ROLE OS Builder output without code changes.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


class Settings:
    """Runtime configuration for the ROLE OS Dashboard."""

    def __init__(self) -> None:
        self.db_path: Path = Path(
            os.environ.get("ROLE_OS_DB_PATH", "samples/role_os_sample/00_SYSTEM/role_os.db")
        ).resolve()
        self.app_name: str = "ROLE OS Dashboard"
        self.app_version: str = "0.1.0"


@lru_cache
def get_settings() -> Settings:
    return Settings()
