"""Integration tests for the Project Intelligence API (/pi/*), Epic 1.

Uses the shared TestClient/app instance (same as test_api.py and
test_ui.py) so this also exercises the real dependency-injected settings
and the isolated temp projects DB set up in conftest.py. Project names use
a per-test unique suffix so tests can run against the shared session DB
without colliding with each other.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def make_project(**overrides) -> dict:
    payload = {"name": unique("Project"), "workspace": "Products", "description": "desc"}
    payload.update(overrides)
    resp = client.post("/pi/projects", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Workspaces
# ---------------------------------------------------------------------------


def test_list_workspaces_includes_defaults():
    resp = client.get("/pi/workspaces")
    assert resp.status_code == 200
    names = {w["name"] for w in resp.json()}
    assert names == {"Personal", "Kontoor", "Unger", "Products", "Ideas", "Library"}


def test_create_workspace_and_get_it():
    name = unique("Workspace")
    resp = client.post("/pi/workspaces", json={"name": name, "description": "test"})
    assert resp.status_code == 201
    workspace = resp.json()

    resp = client.get(f"/pi/workspaces/{workspace['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == name


def test_create_duplicate_workspace_conflicts():
    name = unique("Workspace")
    assert client.post("/pi/workspaces", json={"name": name}).status_code == 201
    assert client.post("/pi/workspaces", json={"name": name}).status_code == 409


def test_get_workspace_404_when_missing():
    assert client.get("/pi/workspaces/does-not-exist").status_code == 404


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------


def test_create_and_get_project():
    project = make_project(owner="Rogelio", tags=["brand"])
    resp = client.get(f"/pi/projects/{project['id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["owner"] == "Rogelio"
    assert body["tags"] == ["brand"]
    assert body["health_score"] == 0


def test_get_project_404_when_missing():
    assert client.get("/pi/projects/does-not-exist").status_code == 404


def test_list_projects_filters_by_workspace():
    name = unique("Filterable")
    make_project(name=name, workspace="Ideas")
    resp = client.get("/pi/projects", params={"workspace": "Ideas"})
    assert resp.status_code == 200
    assert any(p["name"] == name for p in resp.json())


def test_update_project():
    project = make_project()
    resp = client.patch(f"/pi/projects/{project['id']}", json={"status": "at_risk", "priority": "high"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "at_risk"
    assert body["priority"] == "high"


def test_update_project_404_when_missing():
    resp = client.patch("/pi/projects/does-not-exist", json={"status": "paused"})
    assert resp.status_code == 404


def test_delete_project():
    project = make_project()
    assert client.delete(f"/pi/projects/{project['id']}").status_code == 204
    assert client.get(f"/pi/projects/{project['id']}").status_code == 404


# ---------------------------------------------------------------------------
# Collections
# ---------------------------------------------------------------------------


def test_todo_collection_crud():
    project = make_project()
    project_id = project["id"]

    resp = client.post(f"/pi/projects/{project_id}/todos", json={"text": "Finish logo", "status": "open"})
    assert resp.status_code == 201
    todo = resp.json()

    resp = client.get(f"/pi/projects/{project_id}/todos")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    resp = client.patch(f"/pi/projects/{project_id}/todos/{todo['id']}", json={"status": "done"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "done"

    resp = client.delete(f"/pi/projects/{project_id}/todos/{todo['id']}")
    assert resp.status_code == 204
    assert client.get(f"/pi/projects/{project_id}/todos").json() == []


def test_decisions_and_deliverables_collections():
    project = make_project()
    project_id = project["id"]

    resp = client.post(f"/pi/projects/{project_id}/decisions", json={"text": "Use Claude", "status": "resolved"})
    assert resp.status_code == 201

    resp = client.post(
        f"/pi/projects/{project_id}/deliverables", json={"text": "Brand guide", "status": "delivered"}
    )
    assert resp.status_code == 201

    detail = client.get(f"/pi/projects/{project_id}").json()
    assert detail["decisions"][0]["text"] == "Use Claude"
    assert detail["deliverables"][0]["status"] == "delivered"


def test_collection_operations_404_for_missing_project():
    assert client.get("/pi/projects/does-not-exist/notes").status_code == 404
    assert client.post("/pi/projects/does-not-exist/notes", json={"text": "x"}).status_code == 404


def test_conversation_link_lifecycle():
    project = make_project()
    project_id = project["id"]

    resp = client.post(f"/pi/projects/{project_id}/conversations", json={"conversation_id": "conv-1"})
    assert resp.status_code == 201
    assert client.get(f"/pi/projects/{project_id}/conversations").json() == ["conv-1"]

    resp = client.delete(f"/pi/projects/{project_id}/conversations/conv-1")
    assert resp.status_code == 204
    assert client.get(f"/pi/projects/{project_id}/conversations").json() == []


def test_related_project_link_lifecycle():
    a = make_project()
    b = make_project()

    resp = client.post(f"/pi/projects/{a['id']}/related_projects", json={"project_id": b["id"]})
    assert resp.status_code == 201
    assert client.get(f"/pi/projects/{a['id']}/related_projects").json() == [b["id"]]

    resp = client.delete(f"/pi/projects/{a['id']}/related_projects/{b['id']}")
    assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------


def test_capability_lifecycle():
    provider = make_project(name=unique("ROLE Master"))
    consumer = make_project(name=unique("SUPER FACIL"))

    resp = client.post(
        f"/pi/projects/{provider['id']}/capabilities",
        json={"name": "Brand Identity", "description": "Logo + style", "category": "branding"},
    )
    assert resp.status_code == 201
    capability = resp.json()

    resp = client.get(f"/pi/projects/{provider['id']}/capabilities")
    assert resp.status_code == 200
    assert any(c["id"] == capability["id"] for c in resp.json())

    resp = client.post(
        f"/pi/capabilities/{capability['id']}/consume", json={"consumer_project_id": consumer["id"]}
    )
    assert resp.status_code == 201

    resp = client.get(f"/pi/projects/{consumer['id']}/capabilities/consumed")
    assert resp.status_code == 200
    assert any(c["id"] == capability["id"] for c in resp.json())

    resp = client.get(f"/pi/capabilities/{capability['id']}/consumers")
    assert resp.status_code == 200
    assert any(c["consumer_project_id"] == consumer["id"] for c in resp.json())

    resp = client.get("/pi/capabilities", params={"q": "Brand"})
    assert resp.status_code == 200
    assert any(c["id"] == capability["id"] for c in resp.json())

    resp = client.delete(f"/pi/capabilities/{capability['id']}/consume/{consumer['id']}")
    assert resp.status_code == 204


def test_capability_create_404_for_missing_project():
    resp = client.post("/pi/projects/does-not-exist/capabilities", json={"name": "X"})
    assert resp.status_code == 404


def test_capability_consume_404_for_missing_capability_or_project():
    resp = client.post("/pi/capabilities/does-not-exist/consume", json={"consumer_project_id": "nope"})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def test_dependency_lifecycle():
    a = make_project(name=unique("ROLE Master"))
    b = make_project(name=unique("SUPER FACIL"))

    resp = client.post(
        f"/pi/projects/{b['id']}/dependencies",
        json={"depends_on_project_id": a["id"], "note": "needs branding"},
    )
    assert resp.status_code == 201
    dependency = resp.json()

    resp = client.get(f"/pi/projects/{b['id']}/dependencies")
    assert resp.status_code == 200
    assert resp.json()[0]["depends_on_project_name"] == b["name"] or resp.json()[0]["depends_on_project_id"] == a["id"]

    resp = client.get(f"/pi/projects/{a['id']}/dependents")
    assert resp.status_code == 200
    assert any(d["project_id"] == b["id"] for d in resp.json())

    resp = client.delete(f"/pi/projects/{b['id']}/dependencies/{dependency['id']}")
    assert resp.status_code == 204


def test_dependency_rejects_invalid_pair():
    a = make_project()
    resp = client.post(f"/pi/projects/{a['id']}/dependencies", json={"depends_on_project_id": a["id"]})
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


def test_project_health_endpoint_computes_and_persists_score():
    project = make_project()
    resp = client.get(f"/pi/projects/{project['id']}/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["project_id"] == project["id"]
    assert 0 <= body["score"] <= 100
    assert "recent_activity" in body["breakdown"]

    stored = client.get(f"/pi/projects/{project['id']}").json()
    assert stored["health_score"] == body["score"]


def test_health_recalculate_all():
    make_project()
    resp = client.post("/pi/health/recalculate")
    assert resp.status_code == 200
    assert resp.json()["updated"] >= 1


def test_project_health_404_when_missing():
    assert client.get("/pi/projects/does-not-exist/health").status_code == 404


# ---------------------------------------------------------------------------
# Regression: Milestone 1/2 API and UI must be completely unaffected
# ---------------------------------------------------------------------------


def test_existing_endpoints_still_work():
    assert client.get("/health").status_code == 200
    assert client.get("/projects").status_code == 200
    assert client.get("/search", params={"q": "Master"}).status_code == 200
    assert client.get("/knowledge/conv-1").status_code == 200
    assert client.get("/knowledge/does-not-exist").status_code == 404
    assert client.get("/").status_code == 200
    assert client.get("/ui/recent").status_code == 200
    assert client.get("/ui/timeline").status_code == 200
