"""Capability endpoints: a project may expose reusable capabilities that
other projects can consume.

Routes:
    GET  /pi/capabilities                          global list/search
    GET  /pi/projects/{id}/capabilities             capabilities this project provides
    POST /pi/projects/{id}/capabilities             expose a new capability
    GET  /pi/projects/{id}/capabilities/consumed    capabilities this project consumes
    POST /pi/capabilities/{capability_id}/consume   record a consumer
    DELETE /pi/capabilities/{capability_id}/consume/{consumer_project_id}
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import Settings, get_settings
from app.projects import db
from app.projects.models import Capability, CapabilityConsumeRequest, CapabilityCreate

router = APIRouter(tags=["project-intelligence"])


@router.get("/pi/capabilities", response_model=list[Capability])
def list_all_capabilities(
    q: str | None = Query(None), settings: Settings = Depends(get_settings)
) -> list[Capability]:
    return [Capability(**c) for c in db.list_capabilities(q=q, settings=settings)]


@router.get("/pi/projects/{project_id}/capabilities", response_model=list[Capability])
def list_project_capabilities(project_id: str, settings: Settings = Depends(get_settings)) -> list[Capability]:
    if not db.get_project(project_id, settings):
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return [Capability(**c) for c in db.list_capabilities(project_id=project_id, settings=settings)]


@router.post("/pi/projects/{project_id}/capabilities", response_model=Capability, status_code=201)
def create_capability(
    project_id: str, payload: CapabilityCreate, settings: Settings = Depends(get_settings)
) -> Capability:
    created = db.create_capability(project_id, payload.name, payload.description, payload.category, settings)
    if not created:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return Capability(**created)


@router.get("/pi/projects/{project_id}/capabilities/consumed")
def list_consumed_capabilities(project_id: str, settings: Settings = Depends(get_settings)) -> list[dict]:
    if not db.get_project(project_id, settings):
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return db.list_consumed_capabilities(project_id, settings)


@router.post("/pi/capabilities/{capability_id}/consume", status_code=201)
def consume_capability(
    capability_id: str, payload: CapabilityConsumeRequest, settings: Settings = Depends(get_settings)
) -> dict:
    result = db.consume_capability(capability_id, payload.consumer_project_id, settings)
    if not result:
        raise HTTPException(status_code=404, detail="Capability or consumer project not found")
    return result


@router.delete("/pi/capabilities/{capability_id}/consume/{consumer_project_id}", status_code=204)
def remove_capability_consumer(
    capability_id: str, consumer_project_id: str, settings: Settings = Depends(get_settings)
) -> None:
    if not db.remove_capability_consumer(capability_id, consumer_project_id, settings):
        raise HTTPException(status_code=404, detail="Consumption link not found")


@router.get("/pi/capabilities/{capability_id}/consumers")
def list_capability_consumers(capability_id: str, settings: Settings = Depends(get_settings)) -> list[dict]:
    if not db.get_capability(capability_id, settings):
        raise HTTPException(status_code=404, detail=f"Capability '{capability_id}' not found")
    return db.list_capability_consumers(capability_id, settings)
