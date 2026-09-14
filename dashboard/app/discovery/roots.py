"""Phase 2 (Multi-Root Discovery): validates and de-duplicates a list of
configured Discovery roots before `run_audit` is called once per root.

This module answers "which of these configured roots are safe and distinct
to scan?" -- it never scans anything itself (see `app.discovery.service.
run_audit`) and never decides which projects get adopted (see
`app.workspace.service`). Read-only: `Path.resolve()`/`Path.exists()`/
`Path.is_dir()` only.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RootDiagnostic:
    """One configured root that was not scanned, and why."""

    root: str
    reason: str


@dataclass(frozen=True)
class RootsResolution:
    """`valid`: absolute, resolved, deduplicated, non-nested roots -- safe
    to pass to `run_audit`, in the order they were first seen.
    `skipped`: every configured root that was dropped, with a reason
    (nonexistent, not a directory, unresolvable, duplicate, or nested
    inside another configured root) -- surfaced as diagnostics, never
    silently discarded."""

    valid: list[str]
    skipped: list[RootDiagnostic]


def _normalize_key(resolved: Path) -> str:
    """A comparison key that treats Windows drive-letter casing and
    trailing separators as equal, without altering the display string
    used for the actual scan (`str(resolved)` keeps its real casing)."""
    return os.path.normcase(os.path.normpath(str(resolved)))


def resolve_roots(raw_roots: list[str]) -> RootsResolution:
    """Validates and deduplicates `raw_roots` (as configured, in order).

    Two passes:
    1. Resolve each root to an absolute path, dropping anything that
       can't be resolved, doesn't exist, isn't a directory, or normalizes
       to a root already kept (duplicate, including case/slash variants).
    2. Drop any surviving root that is a strict subdirectory of another
       surviving root -- scanning both would let the same project be
       discovered twice, once under each root's own `root_path`.
    """
    skipped: list[RootDiagnostic] = []
    resolved_pairs: list[tuple[str, str]] = []  # (display_str, normalized_key)
    seen_keys: dict[str, str] = {}

    for raw in raw_roots:
        raw = raw.strip()
        if not raw:
            continue
        try:
            resolved = Path(raw).resolve()
        except OSError as exc:
            skipped.append(RootDiagnostic(raw, f"could not resolve path: {exc}"))
            continue
        if not resolved.exists():
            skipped.append(RootDiagnostic(raw, "does not exist"))
            continue
        if not resolved.is_dir():
            skipped.append(RootDiagnostic(raw, "not a directory"))
            continue

        display = str(resolved)
        key = _normalize_key(resolved)
        if key in seen_keys:
            skipped.append(RootDiagnostic(raw, f"duplicate of already-configured root: {seen_keys[key]}"))
            continue
        seen_keys[key] = display
        resolved_pairs.append((display, key))

    valid: list[str] = []
    for display, key in resolved_pairs:
        nested_in = next(
            (
                other_display
                for other_display, other_key in resolved_pairs
                if other_key != key and key.startswith(other_key + os.sep)
            ),
            None,
        )
        if nested_in is not None:
            skipped.append(RootDiagnostic(display, f"nested inside already-configured root: {nested_in}"))
            continue
        valid.append(display)

    return RootsResolution(valid=valid, skipped=skipped)
