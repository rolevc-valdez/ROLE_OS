import json
from pathlib import Path

from app.discovery.detectors.inventory import build_inventory
from app.discovery.detectors.operational_manifest import detect


def test_reads_valid_manifest(tmp_path: Path):
    folder = tmp_path / ".role-os"
    folder.mkdir()
    payload = {"schema_version": 1, "project": "RCF", "status": "active"}
    (folder / "project-status.json").write_text(json.dumps(payload), encoding="utf-8")
    result = detect(build_inventory(tmp_path))
    assert result.operational_manifest == payload
    assert result.operational_manifest_error is None


def test_reports_invalid_manifest_without_raising(tmp_path: Path):
    folder = tmp_path / ".role-os"
    folder.mkdir()
    (folder / "project-status.json").write_text("not json", encoding="utf-8")
    result = detect(build_inventory(tmp_path))
    assert result.operational_manifest == {}
    assert "invalid ROLE OS manifest" in result.operational_manifest_error
