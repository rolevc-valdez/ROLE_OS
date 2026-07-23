# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Added

- Epic 1: Project Intelligence layer. ROLE OS gains first-class Projects,
  Workspaces, Capabilities, Dependencies, and a modular Health Score engine.
  - New domain model under `dashboard/app/projects/`:
    - `db.py` — dashboard-owned SQLite persistence (separate database file,
      `ROLE_OS_PROJECTS_DB_PATH`, from the builder-generated knowledge DB),
      with automatic idempotent schema creation and default-workspace
      seeding (`Personal`, `Kontoor`, `Unger`, `Products`, `Ideas`,
      `Library`) on first use.
    - Every Project has: `id`, `workspace`, `name`, `description`, `status`,
      `health_score`, `priority`, `tags`, `owner`, `created_at`,
      `updated_at`, and collections: `notes`, `decisions`, `todos`,
      `deliverables`, `assets`, `prompts`, `conversations` (linked
      knowledge-base conversation ids), `related_projects`, `capabilities`,
      and `dependencies`.
    - Capabilities: a project may expose reusable capabilities that other
      projects can consume (e.g. `ROLE Master` exposing "Brand Identity",
      consumed by `SUPER FACIL`).
    - Dependencies: projects may depend on one another, fully queryable in
      both directions (`/pi/projects/{id}/dependencies` and
      `/pi/projects/{id}/dependents`).
  - New modular Health Score engine under
    `dashboard/app/projects/health/`: one independent, pure-function signal
    per file (`activity.py`, `todos.py`, `decisions.py`, `deliverables.py`,
    `conversations.py`, `commits.py`), combined by `__init__.py` into a
    weighted 0-100 score that gracefully renormalizes when a signal (e.g.
    commits, with no git integration yet) is unavailable.
  - New Project Intelligence API, entirely additive and namespaced under
    `/pi` to avoid any collision with the existing `/projects` endpoint:
    workspaces, projects (CRUD + filtering), the six collection types,
    conversation/related-project links, capabilities (expose/consume/list),
    dependencies (add/remove/list/reverse-lookup), and health score
    (recompute + persist, single project or bulk).
  - Dashboard UI: a new "Projects" tab alongside the existing "Knowledge"
    tab (plain HTML/CSS/JS, no framework) with a workspace selector, a
    project list with color-coded Health Score indicators, and a project
    detail page showing the health breakdown, capability section
    (provided/consumed), dependency section (depends on/dependents), and
    all collections.
  - The four Milestone 1 API endpoints and the Milestone 2 UI are
    completely unchanged; only new, additive endpoints and UI elements
    were introduced.
  - 61 new tests (unit tests for every health signal and every `db.py`
    function; integration tests for every new `/pi/*` endpoint; a UI test
    for the new Projects tab), for 103/103 passing repo-wide.
  - Updated `dashboard/README.md` and root `README.md`.

- Milestone 3: Knowledge Engine 2.0 — a modular knowledge extraction
  pipeline under `builder/extractors/` that enriches every Knowledge Card.
  - New extractors, one responsibility each: `summary.py`, `decisions.py`
    (decisions + deliverables), `todos.py`, `prompts.py`, `entities.py`
    (people, applications, vendors, urls, files, project/tag
    classification), `relationships.py` (related conversations).
  - `extractors/__init__.py` defines the extended `KnowledgeCard` and
    `build_knowledge_card()`, which merges every extractor's output into
    one card.
  - New fields on every Knowledge Card: real `vendors` extraction
    (previously always empty), `files` (previously only exposed via the
    `assets` alias, which is kept for backward compatibility), and
    `related_conversations` — computed in a second, corpus-level pass
    (`attach_related_conversations`) via weighted overlap of project, tags,
    people, and applications across all cards.
  - New `VENDORS.json` cross-reference index alongside the existing
    PROJECTS/PEOPLE/APPLICATIONS/TAGS/TIMELINE indexes.
  - `builder.py`'s SQLite write (`role_os.db`) now happens after the
    relationship pass, so `related_conversations` and real `vendors` are
    persisted automatically.
  - `knowledge_extractor.py` is now a thin backward-compatible wrapper
    (`build_card`) around `extractors.build_knowledge_card` — the builder
    CLI, its arguments, and its output folder layout are unchanged.
  - No dashboard changes were required: the existing `/knowledge/{id}`
    endpoint already passes new fields through (`extra="allow"`).
  - New regression tests under `builder/tests/`: per-extractor unit tests,
    pipeline tests (including a backward-compatibility check that
    `knowledge_extractor.build_card` matches `extractors.build_knowledge_card`),
    and an end-to-end integration test asserting enriched output and
    updated SQLite.
  - Regenerated `samples/role_os_sample` with the new pipeline.

- Milestone 2: first usable ROLE OS web dashboard, served directly by the
  existing FastAPI app at `/`. Built with plain HTML, CSS, and JavaScript —
  no frontend framework.
  - Global search bar (uses the existing `GET /search?q=` endpoint).
  - Project list with conversation counts (uses the existing `GET /projects`
    endpoint); clicking a project filters the card list.
  - Recent knowledge cards list (new additive `GET /ui/recent` endpoint).
  - Knowledge card detail view/modal showing summary, decisions,
    deliverables, to-dos, people, applications, and tags (uses the existing
    `GET /knowledge/{id}` endpoint).
  - Basic chronological timeline (new additive `GET /ui/timeline` endpoint).
  - The four Milestone 1 API endpoints (`/health`, `/projects`, `/search`,
    `/knowledge/{id}`) are unchanged; `/ui/recent` and `/ui/timeline` are
    additive, UI-only endpoints and do not alter existing API contracts.
  - UI tests (`dashboard/tests/test_ui.py`) covering page rendering, static
    asset serving, the new `/ui/*` endpoints, and a regression check that
    the original API responses are unaffected.

- Repository project structure: `/builder`, `/dashboard`, `/docs`, `/tests`,
  `/scripts`, `/samples`.
- Migrated the existing ROLE OS Builder (`builder.py`,
  `knowledge_extractor.py`, `run_windows.bat`) into `/builder`, unchanged
  functionally, with an updated README and `requirements.txt`.
- New FastAPI dashboard application under `/dashboard` exposing:
  - `GET /health`
  - `GET /projects`
  - `GET /search?q=`
  - `GET /knowledge/{id}`
  Backed by the SQLite database produced by the builder. No AI features.
- Sample ChatGPT export and generated ROLE Knowledge OS output under
  `/samples` for local smoke-testing.
- Repo-level and dashboard-level test suites (pytest).
- Root `README.md`, `pyproject.toml`, and `.gitignore` additions.
