"""Integration tests for Sprint 5 (Project Unification): the canonical
identity bridge, the Resume Work endpoint, and that every existing
AI Sessions/Timeline endpoint works *unmodified* against the resulting
canonical project id. Real Discovery Engine runs throughout -- nothing
mocked.
"""

from __future__ import annotations

from pathlib import Path

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def _write(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_and_adopt(tmp_path: Path, suffix: str, name: str = "app-a") -> dict:
    root = tmp_path / f"scan-root-{suffix}"
    _write(root / name / "README.md", "# A\n")
    _write(root / name / "pyproject.toml", "[project]\nname='a'")
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    item = next(i for i in items if i["name"] == name)
    client.post(f"/workspace/discovered/{item['id']}/adopt", json={})
    return item


def test_resume_work_404_before_adopt(tmp_path):
    root = tmp_path / "scan-root-preadopt"
    _write(root / "app-a" / "README.md", "x")
    _write(root / "app-a" / "pyproject.toml", "[project]\nname='a'")
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    item = items[0]

    resp = client.post(f"/workspace/discovered/{item['id']}/resume-work")
    assert resp.status_code == 404


def test_resume_work_after_adopt_creates_session_with_zero_manual_creation(tmp_path):
    item = _make_and_adopt(tmp_path, "1")
    resp = client.post(f"/workspace/discovered/{item['id']}/resume-work")
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_new_session"] is True
    assert body["item_id"] == item["id"]
    assert body["prompt"]
    assert body["url"]


def test_canonical_project_visible_in_pi_projects(tmp_path):
    item = _make_and_adopt(tmp_path, "2")
    resp = client.post(f"/workspace/discovered/{item['id']}/resume-work")
    canonical_id = resp.json()["project_id"]

    pi_projects = client.get("/pi/projects").json()
    match = next((p for p in pi_projects if p["id"] == canonical_id), None)
    assert match is not None
    assert match["discovery_item_id"] == item["id"]


def test_existing_ai_sessions_endpoints_work_unmodified_against_canonical_id(tmp_path):
    item = _make_and_adopt(tmp_path, "3")
    canonical_id = client.post(f"/workspace/discovered/{item['id']}/resume-work").json()[
        "project_id"
    ]

    sessions = client.get(f"/pi/projects/{canonical_id}/ai-sessions").json()
    assert len(sessions) == 1
    session_id = sessions[0]["id"]

    resume_resp = client.get(f"/pi/projects/{canonical_id}/ai-sessions/{session_id}/resume")
    assert resume_resp.status_code == 200

    snap_resp = client.post(
        f"/pi/projects/{canonical_id}/ai-sessions/{session_id}/snapshots",
        json={"summary": "great progress", "next_prompt": "keep going"},
    )
    assert snap_resp.status_code == 201

    timeline = client.get(f"/pi/projects/{canonical_id}/timeline").json()
    assert len(timeline) == 2  # session started + snapshot


def test_enriched_detail_shows_real_history(tmp_path):
    item = _make_and_adopt(tmp_path, "4")
    client.post(f"/workspace/discovered/{item['id']}/resume-work")

    detail = client.get(f"/workspace/discovered/{item['id']}").json()
    assert detail["canonical_project_id"] is not None
    assert len(detail["ai_sessions"]["sessions"]) == 1
    assert len(detail["timeline"]) == 1


def test_resume_work_idempotent_reuses_session(tmp_path):
    item = _make_and_adopt(tmp_path, "5")
    first = client.post(f"/workspace/discovered/{item['id']}/resume-work").json()
    second = client.post(f"/workspace/discovered/{item['id']}/resume-work").json()
    assert first["session_id"] == second["session_id"]
    assert second["is_new_session"] is False


def test_backward_compat_migration_links_existing_manual_project(tmp_path):
    manual_resp = client.post(
        "/pi/projects", json={"name": "Pre-Existing Sprint5 Match", "workspace": "Products"}
    )
    manual = manual_resp.json()

    root = tmp_path / "scan-root-migration"
    _write(root / "Pre-Existing Sprint5 Match" / "README.md", "x")
    _write(root / "Pre-Existing Sprint5 Match" / "pyproject.toml", "[project]\nname='a'")
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    item = next(i for i in items if i["name"] == "Pre-Existing Sprint5 Match")
    client.post(f"/workspace/discovered/{item['id']}/adopt", json={})

    detail = client.get(f"/workspace/discovered/{item['id']}").json()
    assert detail["canonical_project_id"] == manual["id"]

    # Never destroy user data / never create a duplicate.
    pi_projects = client.get("/pi/projects").json()
    matching = [p for p in pi_projects if p["name"] == "Pre-Existing Sprint5 Match"]
    assert len(matching) == 1


def test_manual_project_without_discovery_link_still_works(tmp_path):
    """Backward compatibility (§7): a manual project with no matching
    discovered folder keeps working exactly as before."""
    resp = client.post(
        "/pi/projects", json={"name": "Purely Manual Project", "workspace": "Products"}
    )
    assert resp.status_code == 201
    project = resp.json()
    assert project["discovery_item_id"] is None

    sessions_resp = client.post(
        f"/pi/projects/{project['id']}/ai-sessions", json={"assistant": "claude", "title": "t"}
    )
    assert sessions_resp.status_code == 201


def test_real_path_with_spaces_and_parentheses(tmp_path):
    root = tmp_path / "My Drive (test@example.com)" / "1 - IA PROJECTS"
    _write(root / "app-a" / "README.md", "x")
    _write(root / "app-a" / "pyproject.toml", "[project]\nname='a'")
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    item = next(i for i in items if i["name"] == "app-a")
    client.post(f"/workspace/discovered/{item['id']}/adopt", json={})

    resp = client.post(f"/workspace/discovered/{item['id']}/resume-work")
    assert resp.status_code == 200


def test_no_scanned_project_files_modified(tmp_path):
    import os

    root = tmp_path / "scan-root-readonly"
    _write(root / "app-a" / "README.md", "x")
    _write(root / "app-a" / "pyproject.toml", "[project]\nname='a'")

    def snapshot():
        snap = set()
        for dirpath, _dirs, files in os.walk(root):
            for name in files:
                fp = Path(dirpath) / name
                st = fp.stat()
                snap.add((str(fp), st.st_mtime, st.st_size))
        return snap

    before = snapshot()
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    item = next(i for i in items if i["name"] == "app-a")
    client.post(f"/workspace/discovered/{item['id']}/adopt", json={})
    client.post(f"/workspace/discovered/{item['id']}/resume-work")
    client.get(f"/workspace/discovered/{item['id']}")
    after = snapshot()
    assert before == after
