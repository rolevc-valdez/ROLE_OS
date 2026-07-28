"""FastAPI application entry point for the ROLE OS Dashboard.

Run with:
    uvicorn app.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.routers import (
    advisor,
    advisor_search,
    conversation_graph,
    extraction,
    graph,
    health,
    imports,
    knowledge,
    projects,
    search,
    settings as settings_router,
    ui,
)
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

# AI Advisor (Epic 2) — additive only, namespaced under /advisor.
app.include_router(advisor.router)

# Advisor Search (Sprint 6) — additive only, namespaced under
# /advisor/search. A separate router from Epic 2's (left untouched):
# keyword/partial-match search over imported conversations and extracted
# knowledge objects. No AI, no NLP, no embeddings, no semantic search.
app.include_router(advisor_search.router)

# Knowledge Graph (Epic 3) — additive only, namespaced under /graph. The
# graph is computed on demand from the Builder, Project Intelligence, and
# Advisor databases -- it introduces no new persisted store of its own.
app.include_router(graph.router)

# ChatGPT Conversation Importer (Sprint B1) — additive only, namespaced under
# /import. Normalizes and persists raw conversation metadata/content into
# its own SQLite file; performs no AI extraction, project matching, or
# graph inference.
app.include_router(imports.router)

# Knowledge Extraction (Sprint 4) — additive only, namespaced under
# /extraction. Rule-based extraction of Project/Person/Task/Decision/Idea/
# Document/Asset objects from imported conversations into its own SQLite
# file; no AI, no summarization, no graph, no advisor.
app.include_router(extraction.router)

# Knowledge Graph (Sprint 5) — additive only, namespaced under
# /conversation-graph. Independent of the Epic 3 /graph API (different
# pipeline, different vocabulary — see app/conversation_graph/__init__.py).
# Computed on demand from the imports and extraction databases; no new
# persisted store, no AI, no inferred relationships.
app.include_router(conversation_graph.router)

# Settings (Sprint 8) — additive only, namespaced under /settings.
# Aggregates existing config/status/version info and offers export/import
# preview and maintenance actions; introduces no new persisted store.
app.include_router(settings_router.router)

app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")
