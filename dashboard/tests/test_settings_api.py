"""Integration tests for the Settings API (/settings/*), Sprint 8:
overview aggregation, export, import preview, and maintenance actions.
No new persistence model is introduced, so these tests mostly assert the
response shape and that nothing here mutates the existing databases.

Uses the shared TestClient/app instance against the isolated temp DBs set
up in conftest.py.
"""

from __future__ import annotations

import io
import json

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------


def test_settings_overview_shape():
    resp = client.get("/settings")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"general", "system", "about", "maintenance"}

    general = body["general"]
    assert general["app_name"] == "ROLE OS"
    assert set(general["database_paths"].keys()) == {
        "builder", "projects", "advisor", "imports", "extraction",
    }
    assert isinstance(general["search_result_limit"], int)

    system = body["system"]
    assert isinstance(system["total_conversations"], int)
    assert isinstance(system["total_extracted_objects"], int)
    assert set(system["database_sizes_bytes"].keys()) == {
        "builder", "projects", "advisor", "imports", "extraction",
    }

    about = body["about"]
    assert about["version"] == general["app_version"]
    assert about["license"]

    maintenance = body["maintenance"]
    assert maintenance["cache_exists"] is True


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def test_settings_export_is_downloadable_json():
    resp = client.get("/settings/export")
    assert resp.status_code == 200
    assert "attachment" in resp.headers["content-disposition"]
    assert resp.headers["content-disposition"].endswith('filename="role_os_settings.json"')

    payload = json.loads(resp.text)
    assert "general" in payload and "about" in payload
    assert "exported_at" in payload


# ---------------------------------------------------------------------------
# Import (validate/preview only, never applied)
# ---------------------------------------------------------------------------


def _upload(data: dict) -> "list":
    body = json.dumps(data).encode("utf-8")
    return client.post(
        "/settings/import",
        files={"file": ("cfg.json", io.BytesIO(body), "application/json")},
    )


def test_settings_import_accepts_flat_object():
    resp = _upload({"search_result_limit": 250, "default_import_path": "/tmp/x"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is True
    assert body["env_vars_to_set"]["ROLE_OS_SEARCH_RESULT_LIMIT"] == 250
    assert body["env_vars_to_set"]["ROLE_OS_DEFAULT_IMPORT_PATH"] == "/tmp/x"


def test_settings_import_accepts_full_export_shape():
    export = client.get("/settings/export").json()
    resp = _upload(export)
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is True
    assert "ROLE_OS_SEARCH_RESULT_LIMIT" in body["env_vars_to_set"]
    for env_var in (
        "ROLE_OS_DB_PATH", "ROLE_OS_PROJECTS_DB_PATH", "ROLE_OS_ADVISOR_DB_PATH",
        "ROLE_OS_IMPORTS_DB_PATH", "ROLE_OS_EXTRACTION_DB_PATH",
    ):
        assert env_var in body["env_vars_to_set"]


def test_settings_import_rejects_invalid_json():
    resp = client.post(
        "/settings/import",
        files={"file": ("cfg.json", io.BytesIO(b"not json"), "application/json")},
    )
    assert resp.status_code == 400


def test_settings_import_rejects_non_object_top_level():
    resp = client.post(
        "/settings/import",
        files={"file": ("cfg.json", io.BytesIO(b"[1, 2, 3]"), "application/json")},
    )
    assert resp.status_code == 400


def test_settings_import_never_applies_to_running_process():
    before = client.get("/settings").json()["general"]["search_result_limit"]
    _upload({"search_result_limit": before + 123})
    after = client.get("/settings").json()["general"]["search_result_limit"]
    assert after == before


# ---------------------------------------------------------------------------
# Maintenance
# ---------------------------------------------------------------------------


def test_settings_rebuild_graph_returns_counts():
    resp = client.post("/settings/maintenance/rebuild-graph")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["nodes"], int)
    assert isinstance(body["edges"], int)
    assert "rebuilt_at" in body


def test_settings_clear_cache():
    resp = client.post("/settings/maintenance/clear-cache")
    assert resp.status_code == 200
    assert resp.json() == {"cleared": True, "cache": "settings"}


# ---------------------------------------------------------------------------
# Zero regressions
# ---------------------------------------------------------------------------


def test_other_existing_endpoints_unaffected():
    assert client.get("/health").status_code == 200
    assert client.get("/advisor/search").status_code == 200
    assert client.get("/conversation-graph").status_code == 200
