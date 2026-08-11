"""FastAPI application entry point for the ROLE OS Dashboard.

Run with:
    uvicorn app.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.executive_decision import api as executive_decision_router
from app.impact_analysis import api as impact_analysis_router
from app.routers import (
    advisor,
    advisor_search,
    assets,
    conversation_graph,
    dashboard,
    explorer,
    extraction,
    graph,
    health,
    imports,
    knowledge,
    mission_control,
    project_context,
    project_ecosystem,
    projects,
    search,
    ui,
    workspace,
)
from app.routers import (
    launcher as launcher_router,
)
from app.routers import (
    session as session_router,
)
from app.routers import (
    settings as settings_router,
)
from app.routers.pi import ai_sessions as pi_ai_sessions
from app.routers.pi import ai_workspace as pi_ai_workspace
from app.routers.pi import capabilities as pi_capabilities
from app.routers.pi import dependencies as pi_dependencies
from app.routers.pi import health as pi_health
from app.routers.pi import projects as pi_projects
from app.routers.pi import reconciliation as pi_reconciliation
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
# Project Identity Reconciliation (Sprint C2.1) -- registered before
# pi_projects.router: its routes live under the same /pi/projects prefix
# (/pi/projects/reconciliation/*) and Starlette matches routes in
# registration order, so this must come first or pi_projects.router's
# GET /{project_id} would swallow "reconciliation" as a project id.
app.include_router(pi_reconciliation.router)
app.include_router(pi_projects.router)
app.include_router(pi_collections_router)
app.include_router(pi_capabilities.router)
app.include_router(pi_dependencies.router)
app.include_router(pi_health.router)

# AI Workspace (ROLE OS v1.3) — additive only, nested under the existing
# /pi/projects/{id} prefix (same pattern as capabilities/dependencies
# above). One new table in the existing role_os_projects.db; no new
# SQLite file, no changes to /launcher/* (v1.2). Left fully intact and
# functional in v1.4 -- see pi_ai_sessions below.
app.include_router(pi_ai_workspace.router)

# AI Sessions + Session Snapshots + Resume Engine + Project Timeline
# (ROLE OS v1.4 "Context Engine") — additive only, nested under the same
# /pi/projects/{id} prefix. Two new tables in the existing
# role_os_projects.db (no new SQLite file); v1.3's AI Workspace data is
# copied into this collection once, at upgrade time, by a tracked
# migration in app.projects.db -- ai_workspace itself is untouched.
app.include_router(pi_ai_sessions.router)

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

# Daily Session (ROLE OS Dashboard MVP) -- additive only, namespaced under
# /session. Owns its own SQLite file (Start/End My Day, the project
# registry); generates the Claude prompt and the Obsidian daily record as
# pure text, calling no AI/LLM API.
app.include_router(session_router.router)

# AI Launcher (ROLE OS v1.2) -- additive only, namespaced under /launcher.
# Reads the active session (app.session) and recent ecosystem decisions;
# owns no persistence of its own. Returns a prompt and target URL(s) only
# -- no clipboard access, browser automation, or OS-level action happens
# in this process; that all happens client-side in static/js/app.js.
app.include_router(launcher_router.router)

# Workspace Adoption (Discovery Engine Sprint 2) -- additive only,
# namespaced under /workspace. Owns its own SQLite file (a cache of the
# last read-only Discovery Engine scan plus a small per-folder overlay);
# never writes into `role_os_projects.db` and never touches the scanned
# filesystem. See app/workspace/__init__.py.
app.include_router(workspace.router)

# ProjectContext (Sprint C1: Consolidation) -- additive only, namespaced
# under /project-context. The single service that assembles everything a
# UI screen needs to describe one project, reusing Discovery/Workspace/
# Project Intelligence/Advisor exactly as they are -- see
# app/project_context/builder.py. No existing endpoint's behavior changes.
app.include_router(project_context.router)

# Dashboard 2.0 (Sprint C2) -- additive only, namespaced under /dashboard.
# One endpoint returning the executive Dashboard's already-shaped summary,
# composed entirely from ProjectContext/workspace.service/workspace.advisor/
# workspace.portfolio/app.db -- no new persisted store, no new scoring.
app.include_router(dashboard.router)

# Explorer 2.0 (Sprint C3) -- additive only, namespaced under /explorer.
# Universal search over every existing domain (Projects, ProjectContext,
# AI Sessions/Snapshots, Commits, Knowledge, Assets, Markdown, Advisor
# recommendations, ...) -- a pure aggregation layer, no new storage. See
# app/explorer/service.py.
app.include_router(explorer.router)

# Assets OS (Sprint C4) -- additive only, namespaced under /assets. The
# canonical asset index/search/preview/override surface -- Explorer's
# Asset results, the Assets gallery, and Project Hub's assets section all
# read through this one router. `GET /workspace/assets` (Sprint 4) keeps
# working unchanged; it already delegates to the same canonical service
# via `app.workspace.assets_index`'s compatibility shim.
app.include_router(assets.router)

# Mission Control (Sprint C5) -- additive only, namespaced under
# /mission-control. The primary Home experience: one endpoint composing
# ProjectContext/Home's ranking/Workspace Advisor/Recent Activity/Daily
# Session into the single daily decision-and-continuation screen -- no new
# ranking engine, no new persisted store. See app/mission_control/service.py.
app.include_router(mission_control.router)

# Project Ecosystem Engine (Sprint C8) -- additive only, namespaced under
# /project-ecosystem. Understands how adopted projects relate to each
# other (dependencies, shared assets/knowledge/documentation/prompts/
# sessions, blocking relationships) from deterministic evidence only --
# reuses ProjectContext/Assets/Knowledge/PI dependencies exactly as they
# are, no new relationship-detection engine, no LLM. See
# app/project_ecosystem/service.py.
app.include_router(project_ecosystem.router)

# Impact Analysis Engine (Sprint C9) -- additive only, namespaced under
# /impact-analysis. Answers "if this project changes, what else is
# affected?" entirely by reading Project Ecosystem's already-computed
# relationship graph (bounded transitive traversal, no new relationship
# detection), ProjectContext, and Operational Intelligence -- no new
# graph, no LLM. See app/impact_analysis/service.py.
app.include_router(impact_analysis_router.router)

# Executive Decision Engine (Sprint C10) -- additive only, namespaced
# under /executive-decision. Answers "what should I work on next?" by
# scoring every adopted project from evidence Project Context/Operational
# Intelligence/Project Ecosystem/Impact Analysis/Project Memory already
# computed -- no new detector, no LLM, no hidden weighting. See
# app/executive_decision/service.py.
app.include_router(executive_decision_router.router)

app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")
