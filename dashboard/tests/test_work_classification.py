"""Phase 3 Task 2 (work classification & completed semantics) tests.

Covers: domain / client_name / kind validation and backwards compatibility,
the additive schema migration on a pre-existing database, recognition of
`completed` (and that it is not `archived`), exclusion of completed work
from every active Mission Control recommendation surface, and a Resume Work
regression. Real Discovery Engine over synthetic folders, no mocking of the
domain logic -- same convention as `test_mission_control_api.py`.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from app.config import Settings
from app.main import app
from app.workspace import classification, db
from fastapi.testclient import TestClient
from pydantic import ValidationError

client = TestClient(app)


def _write(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _scan_and_get(tmp_path: Path, suffix: str, names: list[str]) -> dict[str, dict]:
    """One shared root, one rescan (the scan cache is global -- see
    `test_executive_decision._make_and_adopt_many`), returns items by name."""
    root = tmp_path / f"wc-scan-root-{suffix}"
    for name in names:
        _write(root / name / "README.md", "# A\n")
        _write(root / name / "pyproject.toml", "[project]\nname='a'")
        _write(root / name / "logo.png", "fake-png-bytes")
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    return {n: next(i for i in items if i["name"] == n) for n in names}


def _adopt(item: dict, **payload) -> dict:
    resp = client.post(f"/workspace/discovered/{item['id']}/adopt", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _patch(item: dict, **payload):
    return client.patch(f"/workspace/discovered/{item['id']}", json=payload)


# ---------------------------------------------------------------------------
# Pure vocabulary
# ---------------------------------------------------------------------------


def test_supported_domains_and_kinds_are_exactly_the_approved_set():
    assert classification.DOMAINS == ("KONTOOR", "UNGER", "ROLE PERSONAL", "CLIENTES")
    assert classification.KINDS == ("project", "tool")


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("KONTOOR", "KONTOOR"),
        ("kontoor", "KONTOOR"),
        ("Role Personal", "ROLE PERSONAL"),
        ("role_personal", "ROLE PERSONAL"),
        ("  clientes ", "CLIENTES"),
        (None, None),
        ("", None),
    ],
)
def test_domain_normalization(raw, expected):
    assert classification.normalize_domain(raw) == expected


@pytest.mark.parametrize("bad", ["PERSONAL", "OTHER", "KONTOOR PROJECTS", "unger2"])
def test_unknown_domain_is_rejected_not_guessed(bad):
    with pytest.raises(ValueError):
        classification.normalize_domain(bad)


def test_kind_normalization_and_default():
    assert classification.normalize_kind(None) == "project"
    assert classification.normalize_kind("") == "project"
    assert classification.normalize_kind("TOOL") == "tool"
    with pytest.raises(ValueError):
        classification.normalize_kind("task")  # TASK is deliberately not a kind


def test_completed_is_recognised_and_archived_is_not_completed():
    assert classification.is_completed_status("completed")
    assert classification.is_completed_status(" Completed ")
    assert not classification.is_completed_status("archived")
    assert not classification.is_completed_status("paused")
    assert not classification.is_completed_status("active")
    assert not classification.is_completed_status(None)


# ---------------------------------------------------------------------------
# Persistence + migration (isolated DB files)
# ---------------------------------------------------------------------------


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("ROLE_OS_WORKSPACE_DB_PATH", str(tmp_path / "workspace.db"))
    return Settings()


def test_adopt_defaults_are_unclassified_project(settings):
    overlay = db.adopt("i1", "C:\\proj\\a", settings=settings)
    assert overlay["domain"] is None
    assert overlay["client_name"] is None
    assert overlay["kind"] == "project"


def test_adopt_with_classification_round_trips(settings):
    overlay = db.adopt(
        "i2",
        "C:\\proj\\b",
        domain="clientes",
        client_name="Ferretería VOLT",
        kind="project",
        settings=settings,
    )
    assert overlay["domain"] == "CLIENTES"
    assert overlay["client_name"] == "Ferretería VOLT"


def test_tool_kind_is_representable_in_the_same_table(settings):
    overlay = db.adopt("i3", "C:\\tools\\yt-dlp", kind="tool", domain="ROLE PERSONAL", settings=settings)
    assert overlay["kind"] == "tool"
    assert overlay["adopted"] is True  # same managed-work model, no parallel store


def test_db_layer_rejects_invalid_values(settings):
    with pytest.raises(ValueError):
        db.adopt("i4", "C:\\proj\\d", domain="NOPE", settings=settings)
    with pytest.raises(ValueError):
        db.adopt("i5", "C:\\proj\\e", kind="task", settings=settings)
    with pytest.raises(ValueError):
        db.adopt("i6", "C:\\proj\\f", domain="KONTOOR", client_name="X", settings=settings)
    assert db.get_overlay("i4", settings) is None  # nothing half-written


def test_client_name_not_required_for_other_domains(settings):
    overlay = db.adopt("i7", "C:\\proj\\g", domain="UNGER", settings=settings)
    assert overlay["domain"] == "UNGER"
    assert overlay["client_name"] is None


def test_update_overlay_client_rules(settings):
    db.adopt("i8", "C:\\proj\\h", settings=settings)
    # client_name without CLIENTES is refused
    with pytest.raises(ValueError):
        db.update_overlay("i8", "C:\\proj\\h", {"client_name": "Volt"}, settings)
    # both together is fine
    out = db.update_overlay(
        "i8", "C:\\proj\\h", {"domain": "CLIENTES", "client_name": "Volt"}, settings
    )
    assert (out["domain"], out["client_name"]) == ("CLIENTES", "Volt")
    # moving away from CLIENTES drops the client name
    out = db.update_overlay("i8", "C:\\proj\\h", {"domain": "KONTOOR"}, settings)
    assert (out["domain"], out["client_name"]) == ("KONTOOR", None)
    # explicit None clears back to unclassified
    out = db.update_overlay("i8", "C:\\proj\\h", {"domain": None}, settings)
    assert out["domain"] is None


def test_migration_is_additive_idempotent_and_preserves_existing_rows(tmp_path, monkeypatch):
    """A database created by the previous schema (no classification
    columns) keeps every row and value; existing rows read as unclassified
    PROJECTs; running the migration again is a no-op."""
    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE adopted_projects (
            id TEXT PRIMARY KEY, root_path TEXT UNIQUE NOT NULL,
            adopted INTEGER NOT NULL DEFAULT 0, ignored INTEGER NOT NULL DEFAULT 0,
            priority TEXT NOT NULL DEFAULT 'medium', business_value TEXT NOT NULL DEFAULT 'medium',
            status TEXT NOT NULL DEFAULT 'active', tags TEXT NOT NULL DEFAULT '[]',
            notes TEXT NOT NULL DEFAULT '[]', adopted_at TEXT,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        INSERT INTO adopted_projects
            (id, root_path, adopted, priority, status, tags, notes, created_at, updated_at)
        VALUES ('legacy-1', 'C:\\\\old\\\\p', 1, 'high', 'Completado', '["x"]',
                '[{"id":"n","text":"keep me"}]', 't', 't');
        """
    )
    conn.commit()
    conn.close()

    monkeypatch.setenv("ROLE_OS_WORKSPACE_DB_PATH", str(path))
    settings = Settings()
    for _ in range(2):  # second pass must be a no-op, not an error
        overlay = db.get_overlay("legacy-1", settings)

    assert overlay["priority"] == "high"
    assert overlay["status"] == "Completado"  # legacy text is NOT rewritten/normalised
    assert overlay["tags"] == ["x"]
    assert overlay["notes"][0]["text"] == "keep me"
    assert overlay["domain"] is None and overlay["client_name"] is None
    assert overlay["kind"] == "project"
    # a legacy non-"completed" status word keeps its old meaning
    assert not classification.is_completed_status(overlay["status"])


# ---------------------------------------------------------------------------
# API boundary
# ---------------------------------------------------------------------------


def test_adopt_api_without_classification_is_backwards_compatible(tmp_path):
    items = _scan_and_get(tmp_path, "compat", ["wc-compat"])
    adopted = _adopt(items["wc-compat"])
    assert adopted["domain"] is None
    assert adopted["client_name"] is None
    assert adopted["kind"] == "project"
    assert adopted["status"] == "active"


def test_adopt_and_patch_api_validate_classification(tmp_path):
    items = _scan_and_get(tmp_path, "api", ["wc-api"])
    item = items["wc-api"]
    bad = client.post(f"/workspace/discovered/{item['id']}/adopt", json={"domain": "NOPE"})
    assert bad.status_code == 422
    bad = client.post(
        f"/workspace/discovered/{item['id']}/adopt", json={"domain": "UNGER", "client_name": "X"}
    )
    assert bad.status_code == 422
    _adopt(item)
    assert _patch(item, kind="task").status_code == 422
    assert _patch(item, client_name="Volt").status_code == 422  # stored domain is not CLIENTES
    ok = _patch(item, domain="clientes", client_name="Ferretería VOLT", kind="tool")
    assert ok.status_code == 200
    body = ok.json()
    assert (body["domain"], body["client_name"], body["kind"]) == (
        "CLIENTES",
        "Ferretería VOLT",
        "tool",
    )


def test_project_context_carries_classification_and_completed_flag(tmp_path):
    items = _scan_and_get(tmp_path, "ctx", ["wc-ctx"])
    item = items["wc-ctx"]
    _adopt(item, domain="KONTOOR")
    _patch(item, status="completed")
    contexts = client.get("/project-context").json()
    ctx = next(c for c in contexts if c["display_name"] == "wc-ctx")
    assert ctx["domain"] == "KONTOOR"
    assert ctx["kind"] == "project"
    assert ctx["is_completed"] is True


# ---------------------------------------------------------------------------
# Completed semantics vs. Mission Control
# ---------------------------------------------------------------------------


def _mission_control_project_names(body: dict) -> dict[str, set[str]]:
    def name(ref):
        return (ref or {}).get("display_name")

    return {
        "ranked": {name(rp["project"]) for rp in body["ranked_projects"]},
        "decision": {name(body["executive_decision"].get("recommended_project"))},
        "todays_focus": {name(i.get("project")) for i in body["todays_focus"]},
        "needs_attention": {name(i.get("project")) for i in body["needs_attention"]},
        "primary": {
            ((body["primary_focus"] or {}).get("project_context") or {}).get("display_name")
        },
    }


def test_completed_project_is_excluded_from_every_active_recommendation(tmp_path):
    items = _scan_and_get(tmp_path, "mc", ["wc-done-proj", "wc-live-proj"])
    # Make the soon-to-be-completed project the most attractive one so its
    # absence can only be explained by the completed rule.
    _adopt(items["wc-done-proj"], business_value="critical")
    _adopt(items["wc-live-proj"], business_value="low")

    before = _mission_control_project_names(client.get("/mission-control").json())
    assert "wc-done-proj" in before["ranked"]  # sanity: it competes while active

    assert _patch(items["wc-done-proj"], status="completed").status_code == 200
    body = client.get("/mission-control").json()
    after = _mission_control_project_names(body)

    for surface, names in after.items():
        assert "wc-done-proj" not in names, f"completed project leaked into {surface}"
    assert "wc-live-proj" in after["ranked"]
    assert after["decision"] == {"wc-live-proj"} or "wc-done-proj" not in after["decision"]
    # still tracked / visible for history views: not deleted, not hidden
    assert any(p["display_name"] == "wc-done-proj" for p in body["portfolio"])
    workspace_items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    done = next(i for i in workspace_items if i["name"] == "wc-done-proj")
    assert done["adopted"] is True and done["status"] == "completed"


def test_completed_project_generates_no_workspace_advisor_recommendations(tmp_path):
    items = _scan_and_get(tmp_path, "adv", ["wc-adv-done"])
    _adopt(items["wc-adv-done"])
    _patch(items["wc-adv-done"], status="completed")
    recs = client.get("/workspace/advisor").json()
    recs = recs["recommendations"] if isinstance(recs, dict) else recs
    assert all(r.get("project") != "wc-adv-done" for r in recs)


def test_archived_is_not_completed_and_still_competes_with_penalty(tmp_path):
    items = _scan_and_get(tmp_path, "arch", ["wc-arch-a", "wc-arch-b"])
    _adopt(items["wc-arch-a"])
    _adopt(items["wc-arch-b"])
    _patch(items["wc-arch-a"], status="archived")
    contexts = client.get("/project-context").json()
    ctx = next(c for c in contexts if c["display_name"] == "wc-arch-a")
    assert ctx["is_completed"] is False
    ranked = {
        rp["project"]["display_name"] for rp in client.get("/mission-control").json()["ranked_projects"]
    }
    assert "wc-arch-a" in ranked  # existing behaviour preserved: penalised, not removed


def test_existing_statuses_keep_their_behaviour(tmp_path):
    """paused / blocked stay non-completed and keep competing (with their
    existing score penalties); only `completed` was given new meaning."""
    items = _scan_and_get(tmp_path, "stat", ["wc-st-paused", "wc-st-blocked"])
    _adopt(items["wc-st-paused"], status="paused")
    _adopt(items["wc-st-blocked"], status="blocked")
    contexts = {c["display_name"]: c for c in client.get("/project-context").json()}
    assert contexts["wc-st-paused"]["is_completed"] is False
    assert contexts["wc-st-blocked"]["is_completed"] is False
    ranked = {
        rp["project"]["display_name"] for rp in client.get("/mission-control").json()["ranked_projects"]
    }
    assert {"wc-st-paused", "wc-st-blocked"} <= ranked


def test_completed_tool_is_also_excluded(tmp_path):
    items = _scan_and_get(tmp_path, "tool", ["wc-tool-done"])
    _adopt(items["wc-tool-done"], kind="tool", domain="ROLE PERSONAL")
    _patch(items["wc-tool-done"], status="completed")
    ranked = {
        rp["project"]["display_name"] for rp in client.get("/mission-control").json()["ranked_projects"]
    }
    assert "wc-tool-done" not in ranked


# ---------------------------------------------------------------------------
# Regression: Mission Control shape and Resume Work still work
# ---------------------------------------------------------------------------


def test_mission_control_shape_and_core_sections_unchanged(tmp_path):
    items = _scan_and_get(tmp_path, "shape", ["wc-shape"])
    _adopt(items["wc-shape"], domain="ROLE PERSONAL")
    body = client.get("/mission-control").json()
    assert {
        "primary_focus",
        "todays_focus",
        "since_last_time",
        "snapshot_continuity",
        "daily_session",
        "quick_actions",
        "executive_decision",
        "ranked_projects",
        "total_projects_tracked",
    } <= set(body)
    assert any(q.get("action") == "resume_work" or "resume" in str(q).lower() for q in body["quick_actions"])


def test_resume_work_still_works_for_classified_and_completed_items(tmp_path):
    items = _scan_and_get(tmp_path, "resume", ["wc-resume"])
    item = items["wc-resume"]
    _adopt(item, domain="KONTOOR")
    resp = client.post(f"/workspace/discovered/{item['id']}/resume-work")
    assert resp.status_code == 200, resp.text
    assert resp.json()["item_id"] == item["id"]

    _patch(item, status="completed")  # history stays reachable
    resp = client.post(f"/workspace/discovered/{item['id']}/resume-work")
    assert resp.status_code == 200, resp.text
    assert resp.json()["project_id"]


def test_pydantic_models_reject_bad_input_directly():
    from app.workspace.models import AdoptRequest, OverlayUpdate

    with pytest.raises(ValidationError):
        AdoptRequest(domain="NOPE")
    with pytest.raises(ValidationError):
        AdoptRequest(domain="KONTOOR", client_name="X")
    with pytest.raises(ValidationError):
        OverlayUpdate(kind="task")
    assert AdoptRequest().domain is None and AdoptRequest().kind is None
