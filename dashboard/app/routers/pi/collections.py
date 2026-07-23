"""Generic collection endpoints for a project's notes, decisions, todos,
deliverables, assets, and prompts.

These six collections share identical CRUD behavior (add/list/update/delete
one item), so routes are generated once per field name instead of being
hand-written six times. Each still produces a distinct, concrete URL path
(e.g. `/pi/projects/{id}/todos`, `/pi/projects/{id}/decisions`, ...).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings, get_settings
from app.projects import db
from app.projects.db import COLLECTION_FIELDS
from app.projects.models import CollectionItem, CollectionItemCreate, CollectionItemUpdate

router = APIRouter(prefix="/pi/projects", tags=["project-intelligence"])


def _register_collection_routes(field: str) -> None:
    def list_items(project_id: str, settings: Settings = Depends(get_settings)) -> list[CollectionItem]:
        items = db.list_collection_items(project_id, field, settings)
        if items is None:
            raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
        return [CollectionItem(**i) for i in items]

    def add_item(
        project_id: str, payload: CollectionItemCreate, settings: Settings = Depends(get_settings)
    ) -> CollectionItem:
        data = {k: v for k, v in payload.model_dump().items() if v is not None}
        item = db.add_collection_item(project_id, field, data, settings)
        if item is None:
            raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
        return CollectionItem(**item)

    def update_item(
        project_id: str,
        item_id: str,
        payload: CollectionItemUpdate,
        settings: Settings = Depends(get_settings),
    ) -> CollectionItem:
        patch = {k: v for k, v in payload.model_dump().items() if v is not None}
        item = db.update_collection_item(project_id, field, item_id, patch, settings)
        if item is None:
            raise HTTPException(status_code=404, detail="Item or project not found")
        return CollectionItem(**item)

    def delete_item(project_id: str, item_id: str, settings: Settings = Depends(get_settings)) -> None:
        if not db.delete_collection_item(project_id, field, item_id, settings):
            raise HTTPException(status_code=404, detail="Item or project not found")

    router.add_api_route(
        f"/{{project_id}}/{field}",
        list_items,
        methods=["GET"],
        response_model=list[CollectionItem],
        name=f"list_{field}",
    )
    router.add_api_route(
        f"/{{project_id}}/{field}",
        add_item,
        methods=["POST"],
        response_model=CollectionItem,
        status_code=201,
        name=f"add_{field}_item",
    )
    router.add_api_route(
        f"/{{project_id}}/{field}/{{item_id}}",
        update_item,
        methods=["PATCH"],
        response_model=CollectionItem,
        name=f"update_{field}_item",
    )
    router.add_api_route(
        f"/{{project_id}}/{field}/{{item_id}}",
        delete_item,
        methods=["DELETE"],
        status_code=204,
        name=f"delete_{field}_item",
    )


for _field in COLLECTION_FIELDS:
    _register_collection_routes(_field)
