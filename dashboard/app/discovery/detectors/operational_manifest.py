"""Read a project's explicitly published ROLE OS operational manifest."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from app.discovery.detectors.inventory import FolderInventory


@dataclass
class Findings:
    operational_manifest: dict = field(default_factory=dict)
    operational_manifest_error: str | None = None


def detect(inventory: FolderInventory) -> Findings:
    matches = [record for record in inventory.files if record.path.replace("\\", "/").endswith("/.role-os/project-status.json")]
    if not matches:
        return Findings()
    path = matches[0].path
    try:
        data = json.loads(open(path, encoding="utf-8").read())
    except (OSError, json.JSONDecodeError) as exc:
        return Findings(operational_manifest_error=f"invalid ROLE OS manifest: {exc}")
    if not isinstance(data, dict) or data.get("schema_version") != 1 or not data.get("project"):
        return Findings(operational_manifest_error="invalid ROLE OS manifest schema")
    return Findings(operational_manifest=data)
