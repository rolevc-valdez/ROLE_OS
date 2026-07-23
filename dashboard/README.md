# ROLE OS Dashboard

FastAPI service over the SQLite knowledge base produced by the ROLE OS
Builder (`/builder`), plus — as of Epic 1 — a first-class **Project
Intelligence** layer (Workspaces, Projects, Capabilities, Dependencies, and
a Health Score engine) with its own API and dashboard UI. No AI features
are implemented yet — everything here is plain data access and rule-based
scoring.

## Web UI

Visiting `/` in a browser serves the ROLE OS dashboard: a single responsive
page built with plain HTML, CSS, and JavaScript (no frontend framework),
with two tabs.

### Knowledge tab (Milestone 2)

- **Global search bar** — searches knowledge cards via the existing `/search` endpoint.
- **Knowledge Areas list with counts** — from `/projects`; click one to filter the card list.
- **Recent knowledge cards** — the default card list view, from `/ui/recent`.
- **Knowledge card detail view** — click any card or timeline entry to open a
  detail panel (summary, decisions, deliverables, to-dos, people,
  applications, tags) fetched from `/knowledge/{id}`.
- **Basic timeline** — chronological list of all knowledge cards, from `/ui/timeline`.

### Projects tab (Epic 1)

- **Workspace selector** — filters the project list by workspace, from `/pi/workspaces`.
- **Project list** — cards showing name, workspace, status, priority, and a
  color-coded Health Score ring, from `/pi/projects`.
- **Project page** — click a project to open its detail view: description,
  tags, owner, and a live-recomputed **Health Score indicator** with a
  per-signal breakdown.
- **Capability section** — capabilities the project provides, and
  capabilities it consumes from other projects.
- **Dependency section** — what the project depends on, and what depends on it.
- **Collections** — notes, decisions, open to-dos, deliverables, assets,
  prompts, linked conversations, and related projects.

The page and its assets live under `app/templates/index.html` and
`app/static/{css,js}` and are served directly by FastAPI — no build step or
bundler required.

## API endpoints

### Knowledge API (Milestone 1 — unchanged)

| Method | Path                 | Description                                   |
|--------|----------------------|------------------------------------------------|
| GET    | `/health`            | Service and database connectivity status        |
| GET    | `/projects`          | Knowledge-card projects with conversation counts |
| GET    | `/search?q=`         | Search knowledge cards by title/summary/content |
| GET    | `/knowledge/{id}`    | Full knowledge card by `conversation_id`        |

The UI additionally uses two small, additive endpoints (Milestone 2):

| Method | Path                    | Description                                  |
|--------|-------------------------|-----------------------------------------------|
| GET    | `/ui/recent?limit=`     | Most recent knowledge cards (default 10)      |
| GET    | `/ui/timeline?limit=`   | Chronological list of knowledge cards          |

### Project Intelligence API (Epic 1 — new, namespaced under `/pi`)

Namespaced under `/pi` specifically so it cannot collide with the existing
`/projects` (knowledge-card project counts) endpoint above — these are two
different concepts: `/projects` groups knowledge cards by a classifier
string, while `/pi/projects` are first-class, persisted Project records.

| Method | Path                                                     | Description |
|--------|-----------------------------------------------------------|--------------|
| GET    | `/pi/workspaces`                                            | List workspaces (with project counts) |
| POST   | `/pi/workspaces`                                             | Create a workspace |
| GET    | `/pi/workspaces/{id}`                                         | Get a workspace |
| GET    | `/pi/projects?workspace=&status=&tag=&priority=`               | List projects (filterable) |
| POST   | `/pi/projects`                                                  | Create a project |
| GET    | `/pi/projects/{id}`                                              | Get a project (full detail incl. all collections) |
| PATCH  | `/pi/projects/{id}`                                               | Update project fields |
| DELETE | `/pi/projects/{id}`                                                | Delete a project |
| GET/POST | `/pi/projects/{id}/{notes\|decisions\|todos\|deliverables\|assets\|prompts}` | List / add a collection item |
| PATCH/DELETE | `/pi/projects/{id}/{collection}/{item_id}`                | Update / remove a collection item |
| GET/POST/DELETE | `/pi/projects/{id}/conversations[/{conversation_id}]`  | Link/unlink a knowledge-base conversation |
| GET/POST/DELETE | `/pi/projects/{id}/related_projects[/{project_id}]`    | Link/unlink a related project |
| GET/POST | `/pi/projects/{id}/capabilities`                            | List / expose a capability |
| GET    | `/pi/projects/{id}/capabilities/consumed`                       | Capabilities this project consumes |
| GET    | `/pi/capabilities?q=`                                             | Global capability search |
| POST/DELETE | `/pi/capabilities/{capability_id}/consume[/{project_id}]`   | Record / remove a consumer |
| GET    | `/pi/capabilities/{capability_id}/consumers`                        | Who consumes a capability |
| GET/POST | `/pi/projects/{id}/dependencies`                              | List / add a dependency |
| DELETE | `/pi/projects/{id}/dependencies/{dependency_id}`                    | Remove a dependency |
| GET    | `/pi/projects/{id}/dependents`                                        | Reverse lookup: who depends on this project |
| GET    | `/pi/projects/{id}/health`                                              | Recompute (live) and persist the Health Score |
| POST   | `/pi/health/recalculate`                                                 | Recompute and persist every project's score |

Interactive API docs (including the full Project Intelligence schema) are
available at `/docs` once the app is running.

## Project Intelligence domain (Epic 1)

### Workspaces

Default workspaces (seeded automatically on first run): `Personal`,
`Kontoor`, `Unger`, `Products`, `Ideas`, `Library`.

### Projects

Every project has: `id`, `workspace`, `name`, `description`, `status`,
`health_score`, `priority`, `tags`, `owner`, `created_at`, `updated_at`, and
these collections: `notes`, `decisions`, `todos`, `deliverables`, `assets`,
`prompts`, `conversations` (linked knowledge-base conversation ids),
`related_projects`, `capabilities` (exposed), and `dependencies`.

### Capabilities

A project may expose reusable capabilities (e.g. ROLE Master exposing
"Brand Identity", "Logo", "Master Prompt"). Other projects can consume a
capability from its provider — `SUPER FACIL` consuming `ROLE Master`'s
"Brand Identity" capability, for example.

### Dependencies

Projects may depend on one another (e.g. `SUPER FACIL` depends on `ROLE
Master` and `ROLE Content Factory`). Dependency information is fully
queryable in both directions: `/pi/projects/{id}/dependencies` (what it
depends on) and `/pi/projects/{id}/dependents` (what depends on it).

### Health Score

A modular 0-100 score computed from independent signals, each its own
function under `app/projects/health/`:

- `activity.py` — recency of the project's own last update
- `todos.py` — open TODO count
- `decisions.py` — unresolved (pending) decisions
- `deliverables.py` — missing (undelivered) deliverables
- `conversations.py` — recency of linked knowledge-base conversations
- `commits.py` — recent commits, if a git integration is ever wired up
  (currently always `None`/unavailable — the signal is implemented but has
  no data source yet, so it's excluded from scoring rather than penalizing
  every project)

`app/projects/health/__init__.py` combines whichever signals are available
into one weighted 0-100 score, renormalizing weights over present signals.
Adding a new signal is a matter of writing one new pure function and
registering its weight — nothing else changes.

## Setup

```bash
cd dashboard
python -m venv .venv
source .venv/bin/activate  # .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

## Configuration

| Environment variable          | Default                                                   | Purpose |
|--------------------------------|-------------------------------------------------------------|----------|
| `ROLE_OS_DB_PATH`               | `samples/role_os_sample/00_SYSTEM/role_os.db`                 | Builder-generated knowledge database (read-only from the dashboard's perspective; regenerated by `builder.py`) |
| `ROLE_OS_PROJECTS_DB_PATH`       | `samples/role_os_sample/00_SYSTEM/role_os_projects.db`         | Project Intelligence database (dashboard-owned; schema and default workspaces are created automatically on first use) |

To point the dashboard at a real ROLE Knowledge OS generated by the builder:

```bash
export ROLE_OS_DB_PATH="/path/to/ROLE_KNOWLEDGE_OS/00_SYSTEM/role_os.db"
```

The two databases are intentionally separate: the knowledge DB is
regenerated wholesale each time `builder.py` runs, while the projects DB is
mutated incrementally through the `/pi/*` API and must not be clobbered by
a builder re-run.

## Run

```bash
uvicorn app.main:app --reload
```

Then visit `http://127.0.0.1:8000/` for the dashboard, or
`http://127.0.0.1:8000/health` to check the API directly.

## Project layout

```
dashboard/
  app/
    main.py                  # FastAPI app + router registration + static mount
    config.py                 # Environment-based settings (db paths, static/template dirs)
    db.py                      # Knowledge database access layer (Milestone 1)
    models.py                  # Knowledge API Pydantic response models
    projects/                    # Project Intelligence domain (Epic 1)
      db.py                        # Projects DB: schema, workspaces, projects, capabilities, dependencies
      models.py                     # Project Intelligence Pydantic schemas
      health/                        # Modular Health Score engine
        __init__.py                    # compute_health_score() combiner
        activity.py, todos.py, decisions.py, deliverables.py,
        conversations.py, commits.py      # One independent signal per file
    routers/
      health.py, projects.py, search.py, knowledge.py   # Milestone 1 API (unchanged)
      ui.py                                                # Dashboard page + /ui/recent, /ui/timeline
      pi/                                                    # Project Intelligence routers, namespaced /pi
        workspaces.py, projects.py, collections.py,
        capabilities.py, dependencies.py, health.py
    templates/
      index.html               # Dashboard page (Jinja2): Knowledge tab + Projects tab
    static/
      css/style.css             # Responsive layout, no framework
      js/app.js                  # Knowledge tab JS + Project Intelligence tab JS
  tests/                    # API, UI, Health Score, and Projects DB tests (pytest + TestClient)
  requirements.txt
```
