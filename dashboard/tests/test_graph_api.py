"""Integration tests for the Knowledge Graph API (/graph/*), Epic 3.

Uses the shared TestClient/app instance (same pattern as test_advisor_api.py
and test_pi_api.py) so real Project Intelligence data created through
/pi/* endpoints flows through into the graph.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def make_project(**overrides) -> dict:
    payload = {"name": unique("GraphProject"), "workspace": "Products", "description": "desc"}
    payload.update(overrides)
    resp = client.post("/pi/projects", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_meta_types_lists_all_12_node_and_relationship_types():
    resp = client.get("/graph/meta/types")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["node_types"]) == 12
    assert len(data["relationship_types"]) == 12


def test_get_graph_returns_nodes_and_edges():
    make_project()
    resp = client.get("/graph")
    assert resp.status_code == 200
    data = resp.json()
    assert "nodes" in data and "edges" in data
    assert any(n["type"] == "Project" for n in data["nodes"])


def test_get_graph_filters_by_node_type():
    make_project()
    resp = client.get("/graph", params={"node_type": "Workspace"})
    assert resp.status_code == 200
    data = resp.json()
    assert all(n["type"] == "Workspace" for n in data["nodes"])


def test_get_node_returns_404_for_unknown_id():
    resp = client.get("/graph/node/project:does-not-exist")
    assert resp.status_code == 404


def test_get_node_returns_node_and_edges_for_known_project():
    project = make_project()
    resp = client.get(f"/graph/node/project:{project['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["node"]["label"] == project["name"]
    assert any(e["type"] == "BELONGS_TO" for e in data["edges"])


def test_project_subgraph_endpoint():
    project = make_project()
    resp = client.get(f"/graph/project/{project['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert any(n["type"] == "Project" for n in data["nodes"])


def test_project_subgraph_404_for_unknown_project():
    resp = client.get("/graph/project/does-not-exist")
    assert resp.status_code == 404


def test_neighbors_endpoint():
    project_a = make_project()
    project_b = make_project()
    dep_payload = {"depends_on_project_id": project_a["id"], "note": "needs it"}
    resp = client.post(f"/pi/projects/{project_b['id']}/dependencies", json=dep_payload)
    assert resp.status_code == 201, resp.text

    resp = client.get(f"/graph/neighbors/project:{project_b['id']}", params={"edge_type": "DEPENDS_ON"})
    assert resp.status_code == 200
    data = resp.json()
    assert any(e["node"]["label"] == project_a["name"] for e in data)


def test_neighbors_404_for_unknown_node():
    resp = client.get("/graph/neighbors/project:does-not-exist")
    assert resp.status_code == 404


def test_path_endpoint_between_dependent_projects():
    project_a = make_project()
    project_b = make_project()
    client.post(
        f"/pi/projects/{project_b['id']}/dependencies",
        json={"depends_on_project_id": project_a["id"]},
    )
    resp = client.get(
        "/graph/path", params={"source": f"project:{project_b['id']}", "target": f"project:{project_a['id']}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["found"] is True
    assert data["edges"][0]["type"] == "DEPENDS_ON"


def test_path_endpoint_404_for_unknown_node():
    project = make_project()
    resp = client.get("/graph/path", params={"source": f"project:{project['id']}", "target": "project:nope"})
    assert resp.status_code == 404


def test_impact_endpoint():
    project = make_project()
    resp = client.get(f"/graph/impact/project:{project['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["origin"]["label"] == project["name"]
    assert "advisor_recommendations" in data


def test_impact_endpoint_404_for_unknown_node():
    resp = client.get("/graph/impact/project:does-not-exist")
    assert resp.status_code == 404


def test_search_endpoint():
    project = make_project(name=unique("SearchableProjectName"))
    resp = client.get("/graph/search", params={"q": "SearchableProjectName"})
    assert resp.status_code == 200
    data = resp.json()
    assert any(project["name"] == n["label"] for n in data)


def test_existing_routes_are_unaffected_by_graph_addition():
    """Regression guard: adding /graph/* must not break Milestones 1-2 or
    Epics 1-2 routes."""
    for path in ("/health", "/projects", "/pi/projects", "/advisor/recommendations", "/"):
        resp = client.get(path)
        assert resp.status_code == 200, f"{path} returned {resp.status_code}"
