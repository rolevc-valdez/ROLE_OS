"""Configurable folder exclusions (§5 of the Sprint 3 brief).

One source-of-truth configuration file, `exclusions_config.json`, sitting
next to this module -- exact names, case-insensitive names, glob patterns,
and relative-path patterns. User-supplied extra exclusions are passed in
as plain strings (never an absolute path) by the caller (see
`app.discovery.service.run_audit`'s `extra_exclusions` parameter, threaded
from `Settings.discovery_extra_exclusions` at the workspace layer) rather
than read from an environment variable here, so this package stays free of
any dependency on `app.config` -- exactly like every other module in
`app.discovery`.
"""

from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

_CONFIG_PATH = Path(__file__).parent / "exclusions_config.json"


@dataclass
class ExclusionConfig:
    exact_names: set[str] = field(default_factory=set)
    case_insensitive_names: set[str] = field(default_factory=set)
    glob_patterns: list[str] = field(default_factory=list)
    relative_path_patterns: list[str] = field(default_factory=list)


@lru_cache(maxsize=1)
def load_exclusion_config() -> ExclusionConfig:
    data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    return ExclusionConfig(
        exact_names=set(data.get("exact_names", [])),
        case_insensitive_names={n.lower() for n in data.get("case_insensitive_names", [])},
        glob_patterns=list(data.get("glob_patterns", [])),
        relative_path_patterns=list(data.get("relative_path_patterns", [])),
    )


def _relative_posix(path: Path, scan_root: Path) -> str:
    try:
        return path.relative_to(scan_root).as_posix()
    except ValueError:
        return path.name


def is_excluded(
    path: Path, scan_root: Path, extra_exclusions: list[str] | None = None
) -> tuple[bool, str | None]:
    """Returns (excluded, reason). Pure name/path matching -- no filesystem
    read beyond what the caller already has (`path.name`)."""
    cfg = load_exclusion_config()
    name = path.name
    rel = _relative_posix(path, scan_root)

    if name in cfg.exact_names:
        return True, f"matches default exclusion (exact name): '{name}'"
    if name.lower() in cfg.case_insensitive_names:
        return True, f"matches default exclusion (case-insensitive name): '{name}'"
    for pattern in cfg.glob_patterns:
        if fnmatch.fnmatch(name, pattern):
            return True, f"matches default exclusion (glob pattern '{pattern}')"
    for pattern in cfg.relative_path_patterns:
        if fnmatch.fnmatch(rel, pattern):
            return True, f"matches default exclusion (relative-path pattern '{pattern}')"

    for extra in extra_exclusions or []:
        if extra == name or extra.lower() == name.lower():
            return True, f"matches user-configured exclusion: '{extra}'"
        if fnmatch.fnmatch(name, extra) or fnmatch.fnmatch(rel, extra):
            return True, f"matches user-configured exclusion pattern: '{extra}'"

    return False, None
