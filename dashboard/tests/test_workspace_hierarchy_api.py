"""Integration tests for the Sprint 3 Workspace Adoption hierarchy/override
API additions: `GET /workspace/discovered?view=...` and the
`/discovered/{id}/override` endpoints. Real Discovery Engine runs against
folders each test creates itself -- nothing mocked.
"""

from __future__ import annotations

from pathlib import Path

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def _write(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_root(tmp_path: Path, suffix: str) -> Path:
    root = tmp_path / f"scan-root-{suffix}"
    _write(root / "Commerce Factory" / "adapter-a" / "package.json", "{}")
    _write(root / "Commerce Factory" / "adapter-b" / "package.json", "{}")
    _write(root / "OTROS - no proyectos" / "junk.txt", "j")
    return root


def test_default_view_unchanged_flat_contract(tmp_path):
    root = _make_root(tmp_path, "1")
    client.post("/workspace/rescan", json={"root": str(root)})

    resp = client.get("/workspace/discovered")
    assert resp.status_code == 200
    items = resp.json()
    # Flat, includes everything -- Commerce Factory + 2 adapters + OTROS.
    assert len(items) == 4


def test_view_top_level_excludes_children_and_excluded(tmp_path):
    root = _make_root(tmp_path, "2")
    client.post("/workspace/rescan", json={"root": str(root)})

    resp = client.get("/workspace/discovered", params={"view": "top_level"})
    assert resp.status_code == 200
    items = resp.json()
    names = {i["name"] for i in items}
    assert names == {"Commerce Factory"}
    assert items[0]["component_count"] == 2
    assert len(items[0]["children"]) == 2


def test_view_excluded(tmp_path):
    root = _make_root(tmp_path, "3")
    client.post("/workspace/rescan", json={"root": str(root)})

    resp = client.get("/workspace/discovered", params={"view": "excluded"})
    assert resp.status_code == 200
    items = resp.json()
    assert any(i["name"] == "OTROS - no proyectos" for i in items)
    for i in items:
        assert i["exclusion_reason"] is not None


def test_view_repositories(tmp_path):
    root = _make_root(tmp_path, "4")
    client.post("/workspace/rescan", json={"root": str(root)})

    resp = client.get("/workspace/discovered", params={"view": "repositories"})
    assert resp.status_code == 200
    items = resp.json()
    assert {i["name"] for i in items} == {"adapter-a", "adapter-b"}
    assert all(i["parent_name"] == "Commerce Factory" for i in items)


def test_invalid_view_returns_400(tmp_path):
    root = _make_root(tmp_path, "5")
    client.post("/workspace/rescan", json={"root": str(root)})

    resp = client.get("/workspace/discovered", params={"view": "bogus"})
    assert resp.status_code == 400


def test_override_top_level_then_clear_roundtrip(tmp_path):
    root = _make_root(tmp_path, "6")
    client.post("/workspace/rescan", json={"root": str(root)})
    repos = client.get("/workspace/discovered", params={"view": "repositories"}).json()
    adapter = next(r for r in repos if r["name"] == "adapter-a")

    resp = client.post(
        f"/workspace/discovered/{adapter['id']}/override", json={"action": "top_level"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["effective_is_top_level_project"] is True
    assert body["item_kind"] == "component"  # untouched computed field

    top = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    assert any(t["name"] == "adapter-a" for t in top)

    resp = client.post(f"/workspace/discovered/{adapter['id']}/override/clear")
    assert resp.status_code == 200
    assert resp.json()["effective_is_top_level_project"] is False


def test_override_attach_to_parent_requires_parent_id(tmp_path):
    root = _make_root(tmp_path, "7")
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered").json()
    target = items[0]

    resp = client.post(
        f"/workspace/discovered/{target['id']}/override", json={"action": "attach_to_parent"}
    )
    assert resp.status_code == 400


def test_override_invalid_action_rejected(tmp_path):
    root = _make_root(tmp_path, "8")
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered").json()
    target = items[0]

    resp = client.post(f"/workspace/discovered/{target['id']}/override", json={"action": "delete"})
    assert resp.status_code == 400


def test_override_unknown_id_returns_404():
    resp = client.post(
        "/workspace/discovered/does-not-exist/override", json={"action": "top_level"}
    )
    assert resp.status_code == 404


def test_override_clear_unknown_id_returns_404():
    resp = client.post("/workspace/discovered/does-not-exist/override/clear")
    assert resp.status_code == 404
