"""FastAPI application entry point for the ROLE OS Dashboard.

Run with:
    uvicorn app.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.routers import health, knowledge, projects, search, ui
from app.routers.pi import capabilities as pi_capabilities
from app.routers.pi import dependencies as pi_dependencies
from app.routers.pi import health as pi_health
from app.routers.pi import projects as pi_projects
from app.routers.pi import workspaces as pi_workspaces
from app.routers.pi.collections import router as pi_collections_router

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Read-only API and web UI over the ROLE OS Builder SQLite knowledge base.",
)

# Public JSON API — unchanged from Milestone 1.
app.include_router(health.router)
app.include_router(projects.router)
app.include_router(search.router)
app.include_router(knowledge.router)

# Web UI — page route + small additive JSON endpoints for the page's JS.
app.include_router(ui.router)

# Project Intelligence (Epic 1) — additive only, namespaced under /pi so it
# cannot collide with any existing route.
app.include_router(pi_workspaces.router)
app.include_router(pi_projects.router)
app.include_router(pi_collections_router)
app.include_router(pi_capabilities.router)
app.include_router(pi_dependencies.router)
app.include_router(pi_health.router)

app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")
