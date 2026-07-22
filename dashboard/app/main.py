"""FastAPI application entry point for the ROLE OS Dashboard.

Run with:
    uvicorn app.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.routers import health, knowledge, projects, search, ui

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

app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")
