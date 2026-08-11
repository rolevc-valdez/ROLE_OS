"""Integration tests for the ProjectContext API (Sprint C1: Consolidation)
-- `GET /project-context` and `GET /project-context/{identifier}`. Real
Discovery Engine runs throughout -- nothing mocked.
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


def test_unknown_identifier_returns_404():
    resp = client.get("/project-context/does-not-exist-at-all")
    assert resp.status_code == 404


def test_get_by_item_id_and_by_canonical_project_id_agree(tmp_path):
    item = _make_and_adopt(tmp_path, "1")
    by_item = client.get(f"/project-context/{item['id']}")
    assert by_item.status_code == 200
    body = by_item.json()
    assert body["item_id"] == item["id"]

    by_project = client.get(f"/project-context/{body['id']}")
    assert by_project.status_code == 200
    assert by_project.json()["id"] == body["id"]


def test_list_endpoint_returns_only_adopted_by_default(tmp_path):
    _make_and_adopt(tmp_path, "2", name="adopted-one")
    root = tmp_path / "scan-root-unadopted"
    _write(root / "unadopted-one" / "README.md", "x")
    _write(root / "unadopted-one" / "pyproject.toml", "[project]\nname='a'")
    client.post("/workspace/rescan", json={"root": str(root)})

    resp = client.get("/project-context")
    assert resp.status_code == 200
    names = [c["display_name"] for c in resp.json()]
    assert "unadopted-one" not in names


def test_resume_work_then_context_shows_real_session_and_timeline(tmp_path):
    item = _make_and_adopt(tmp_path, "3")
    resume_resp = client.post(f"/workspace/discovered/{item['id']}/resume-work")
    assert resume_resp.status_code == 200

    ctx = client.get(f"/project-context/{item['id']}").json()
    assert ctx["latest_ai_session"] is not None
    assert ctx["resume_state"]["session_id"] == resume_resp.json()["session_id"]
    # Sprint C1B: `resume_state` is a real, read-only preview of
    # `workspace.resume.preview_resume_state` (mirroring `resume_work`'s
    # own field names), not the C1 stub's `needs_new_session` boolean.
    assert ctx["resume_state"]["is_new_session_needed"] is False
    assert ctx["resume_state"]["has_snapshot"] is False
    assert len(ctx["timeline"]) >= 1


def test_manual_project_context_via_pi_endpoint(tmp_path):
    manual = client.post(
        "/pi/projects", json={"name": "Manual C1 Test", "workspace": "Products"}
    ).json()
    ctx = client.get(f"/project-context/{manual['id']}")
    assert ctx.status_code == 200
    body = ctx.json()
    assert body["is_discovered"] is False
    assert body["display_name"] == "Manual C1 Test"


def test_no_scanned_project_file_ever_modified(tmp_path):
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
    client.get(f"/project-context/{item['id']}")
    client.get("/project-context")
    after = snapshot()
    assert before == after
