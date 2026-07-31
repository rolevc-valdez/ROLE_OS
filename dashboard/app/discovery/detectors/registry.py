"""The detector registry: an explicit, ordered list of independent,
single-responsibility detectors, each a pure function
`(FolderInventory) -> Findings` where `Findings` is a small dataclass
naming exactly the `DiscoveredProject` fields that detector owns.

Adding a new detector means: write a new module with its own `Findings`
dataclass and `detect()` function (see any module in this package for the
shape), then add one line to `DETECTOR_REGISTRY` below. Nothing else
changes -- no shared orchestration function needs editing, and
`run_all()`'s collision guard means two detectors can never silently
clobber the same field.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Callable

from app.discovery.detectors import (
    absolute_paths,
    assets,
    ci,
    databases,
    docker,
    documentation,
    environment,
    markers,
    obsidian,
    scripts,
    testing,
    vscode_workspace,
)
from app.discovery.detectors.inventory import FolderInventory

DetectorFn = Callable[[FolderInventory], Any]

# (detector name, detect function). Order is not significant for
# correctness -- every detector is independent and order-agnostic by
# construction (see `run_all`'s collision guard) -- but is kept
# alphabetical-ish here for readability.
DETECTOR_REGISTRY: list[tuple[str, DetectorFn]] = [
    ("documentation", documentation.detect),
    ("testing", testing.detect),
    ("environment", environment.detect),
    ("batch_scripts", scripts.detect_batch),
    ("powershell_scripts", scripts.detect_powershell),
    ("docker", docker.detect),
    ("ci", ci.detect),
    ("databases", databases.detect),
    ("obsidian", obsidian.detect),
    ("vscode_workspace", vscode_workspace.detect),
    ("markers", markers.detect),
    ("assets", assets.detect),
    ("absolute_paths", absolute_paths.detect),
]


class DetectorFieldCollisionError(RuntimeError):
    """Raised when two registered detectors claim the same
    `DiscoveredProject` field -- a configuration error in the registry
    itself, not something that can happen from folder contents."""


def run_all(inventory: FolderInventory) -> dict[str, Any]:
    """Run every registered detector over one shared inventory and return
    the merged `DiscoveredProject` field updates as a single dict.

    Each detector's `Findings` dataclass fields are claimed exclusively --
    if two detectors ever declare the same field name, this raises
    `DetectorFieldCollisionError` instead of letting the later one silently
    win, so a copy-paste mistake when adding a new detector fails loudly
    at scan time instead of quietly corrupting another detector's data.
    """
    merged: dict[str, Any] = {}
    owners: dict[str, str] = {}

    for name, detect_fn in DETECTOR_REGISTRY:
        findings = detect_fn(inventory)
        for f in dataclasses.fields(findings):
            if f.name in owners:
                raise DetectorFieldCollisionError(
                    f"detector '{name}' claims field '{f.name}', already claimed "
                    f"by detector '{owners[f.name]}'"
                )
            owners[f.name] = name
            merged[f.name] = getattr(findings, f.name)

    return merged
