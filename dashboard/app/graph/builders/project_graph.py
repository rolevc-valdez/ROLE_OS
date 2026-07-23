"""Builds Project, Workspace, Decision, Deliverable, Prompt, and Asset nodes
straight from the Project Intelligence database, plus the edges that are
intrinsic to a single project's own record:

- Project -[BELONGS_TO]-> Workspace
- Project -[RELATED_TO]-> Project        (related_projects field)
- Project -[REFERENCES]-> Decision|Deliverable|Prompt|Asset  (own collections)

Capability/Dependency/People/Application/Vendor/Conversation edges live in
their own builder modules so each file stays focused on one relationship
family.
"""

from __future__ import annotations

from typing import Any

from app.graph.models import Edge, Node, node_id


def _collection_label(item: dict[str, Any]) -> str:
    return item.get("text") or item.get("name") or item.get("url") or "(untitled)"


def build(projects: list[dict[str, Any]], workspaces: list[dict[str, Any]]) -> tuple[list[Node], list[Edge]]:
    nodes: list[Node] = []
    edges: list[Edge] = []

    for ws in workspaces:
        nodes.append(
            Node(
                id=node_id("Workspace", ws["id"]),
                type="Workspace",
                label=ws["name"],
                data={"description": ws.get("description", ""), "project_count": ws.get("project_count", 0)},
            )
        )

    for project in projects:
        pid = node_id("Project", project["id"])
        nodes.append(
            Node(
                id=pid,
                type="Project",
                label=project["name"],
                data={
                    "project_id": project["id"],
                    "workspace": project.get("workspace"),
                    "status": project.get("status"),
                    "priority": project.get("priority"),
                    "health_score": project.get("health_score", 0),
                    "owner": project.get("owner", ""),
                    "tags": project.get("tags", []),
                },
            )
        )

        ws_name = project.get("workspace")
        ws_match = next((w for w in workspaces if w["name"] == ws_name), None)
        if ws_match:
            edges.append(Edge(source=pid, target=node_id("Workspace", ws_match["id"]), type="BELONGS_TO"))

        for related_id in project.get("related_projects", []) or []:
            edges.append(
                Edge(source=pid, target=node_id("Project", related_id), type="RELATED_TO", data={"via": "related_projects"})
            )

        for item in project.get("decisions", []) or []:
            nid = node_id("Decision", item["id"])
            nodes.append(Node(id=nid, type="Decision", label=_collection_label(item), data=dict(item)))
            edges.append(Edge(source=pid, target=nid, type="REFERENCES"))

        for item in project.get("deliverables", []) or []:
            nid = node_id("Deliverable", item["id"])
            nodes.append(Node(id=nid, type="Deliverable", label=_collection_label(item), data=dict(item)))
            edges.append(Edge(source=pid, target=nid, type="REFERENCES"))

        for item in project.get("prompts", []) or []:
            nid = node_id("Prompt", item["id"])
            nodes.append(Node(id=nid, type="Prompt", label=_collection_label(item), data=dict(item)))
            edges.append(Edge(source=pid, target=nid, type="REFERENCES"))

        for item in project.get("assets", []) or []:
            nid = node_id("Asset", item["id"])
            nodes.append(Node(id=nid, type="Asset", label=_collection_label(item), data=dict(item)))
            edges.append(Edge(source=pid, target=nid, type="REFERENCES"))

    return nodes, edges
