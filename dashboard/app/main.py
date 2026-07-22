"""FastAPI application entry point for the ROLE OS Dashboard.

Run with:
    uvicorn app.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI

from app.config import get_settings
from app.routers import health, knowledge, projects, search

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Read-only API over the ROLE OS Builder SQLite knowledge base.",
)

app.include_router(health.router)
app.include_router(projects.router)
app.include_router(search.router)
app.include_router(knowledge.router)
