"""Integration tests for the Workspace Adoption API (/workspace/*).

Uses the shared TestClient/app instance (same pattern as test_advisor_api.py)
against the real, read-only Discovery Engine -- every test scans a real
temporary folder tree it creates itself; nothing here is mocked.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _write(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_root(tmp_path: Path, suffix: str) -> Path:
    root = tmp_path / f"scan-root-{suffix}"
    _write(root / "alpha-app" / "pyproject.toml", "[project]\nname='alpha'")
    _write(root / "alpha-app" / "main.py", "print(1)\n")
    _write(root / "beta-docs" / "README.md", "hello")
    _write(root / "beta-docs" / "ROADMAP.md", "plans")
    return root


def test_rescan_then_summary(tmp_path):
    root = _make_root(tmp_path, "1")
    resp = client.post("/workspace/rescan", json={"root": str(root)})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["projects_found"] == 2

    summary = client.get("/workspace/summary").json()
    assert summary["projects_found"] == 2
    assert summary["root"] == str(root)


def test_rescan_invalid_root_returns_400():
    resp = client.post("/workspace/rescan", json={"root": "C:\\this\\does\\not\\exist\\at\\all"})
    assert resp.status_code == 400


def test_list_discovered_shows_required_fields(tmp_path):
    root = _make_root(tmp_path, "2")
    client.post("/workspace/rescan", json={"root": str(root)})

    resp = client.get("/workspace/discovered")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2
    for item in items:
        for field in (
            "name",
            "root_path",
            "classification",
            "git_is_repo",
            "health_score",
            "confidence_score",
            "move_risk",
            "adopted",
            "ignored",
        ):
            assert field in item


def test_adopt_ignore_review_flow(tmp_path):
    root = _make_root(tmp_path, "3")
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered").json()
    alpha = next(i for i in items if i["name"] == "alpha-app")
    beta = next(i for i in items if i["name"] == "beta-docs")

    # Adopt
    resp = client.post(
        f"/workspace/discovered/{alpha['id']}/adopt",
        json={"priority": "high", "business_value": "high", "status": "active", "tags": ["client"]},
    )
    assert resp.status_code == 200
    adopted = resp.json()
    assert adopted["adopted"] is True
    assert adopted["priority"] == "high"
    assert adopted["tags"] == ["client"]
    # No metadata duplication: name/health/git are still the live discovery
    # values, not something the adopt call could have overridden.
    assert adopted["name"] == "alpha-app"

    # Ignore
    resp = client.post(f"/workspace/discovered/{beta['id']}/ignore")
    assert resp.status_code == 200
    assert resp.json()["ignored"] is True

    # Ignored project is hidden from the default list
    visible = client.get("/workspace/discovered").json()
    assert beta["id"] not in {i["id"] for i in visible}
    visible_all = client.get("/workspace/discovered?include_ignored=true").json()
    assert beta["id"] in {i["id"] for i in visible_all}

    # Review = read-only detail fetch, full discovery signal set included
    resp = client.get(f"/workspace/discovered/{alpha['id']}")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["id"] == alpha["id"]
    assert "discovery_detail" in detail
    assert detail["discovery_detail"]["root_path"] == alpha["root_path"]


def test_unignore(tmp_path):
    root = _make_root(tmp_path, "4")
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered").json()
    target = items[0]

    client.post(f"/workspace/discovered/{target['id']}/ignore")
    resp = client.post(f"/workspace/discovered/{target['id']}/unignore")
    assert resp.status_code == 200
    assert resp.json()["ignored"] is False

    visible = client.get("/workspace/discovered").json()
    assert target["id"] in {i["id"] for i in visible}


def test_unignore_unknown_id_returns_404():
    resp = client.post("/workspace/discovered/does-not-exist/unignore")
    assert resp.status_code == 404


def test_adopt_unknown_id_returns_404():
    resp = client.post("/workspace/discovered/does-not-exist/adopt", json={})
    assert resp.status_code == 404


def test_get_discovered_unknown_id_returns_404():
    resp = client.get("/workspace/discovered/does-not-exist")
    assert resp.status_code == 404


def test_patch_overlay(tmp_path):
    root = _make_root(tmp_path, "5")
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered").json()
    target = items[0]

    client.post(f"/workspace/discovered/{target['id']}/adopt", json={})
    resp = client.patch(f"/workspace/discovered/{target['id']}", json={"status": "paused"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "paused"


def test_add_note_endpoint(tmp_path):
    root = _make_root(tmp_path, "6")
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered").json()
    target = items[0]

    client.post(f"/workspace/discovered/{target['id']}/adopt", json={})
    resp = client.post(f"/workspace/discovered/{target['id']}/notes", json={"text": "hello note"})
    assert resp.status_code == 200
    assert resp.json()["notes"][0]["text"] == "hello note"


def test_adopted_projects_endpoint_shape(tmp_path):
    root = _make_root(tmp_path, "7")
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered").json()
    target = items[0]
    client.post(
        f"/workspace/discovered/{target['id']}/adopt",
        json={"priority": "medium", "business_value": "high"},
    )

    resp = client.get("/workspace/adopted")
    assert resp.status_code == 200
    projects = resp.json()
    assert len(projects) == 1
    p = projects[0]
    assert p["workspace"] == "Discovered"
    assert p["is_discovered"] is True
    assert "health_score" in p and "priority" in p and "tags" in p


def test_manual_projects_api_still_works_after_workspace_feature(tmp_path):
    """Existing manually-created Project Intelligence records must be
    completely unaffected by Workspace Adoption (separate DB, separate
    tables, separate router)."""
    resp = client.post(
        "/pi/projects",
        json={"name": "Still Works Manually", "workspace": "Products", "description": "d"},
    )
    assert resp.status_code == 201, resp.text
    project = resp.json()
    assert project["name"] == "Still Works Manually"

    listed = client.get("/pi/projects").json()
    assert any(p["id"] == project["id"] for p in listed)
