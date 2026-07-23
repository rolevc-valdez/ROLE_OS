# ROLE OS Dashboard

FastAPI service over the SQLite knowledge base produced by the ROLE OS
Builder (`/builder`), a first-class **Project Intelligence** layer (Epic 1:
Workspaces, Projects, Capabilities, Dependencies, a Health Score engine),
an explainable **AI Advisor** (Epic 2) that recommends what to do next, and
— as of Epic 3 — a **Knowledge Graph** engine that turns all of the above
into one unified, queryable relationship graph. No external AI/LLM API is
called anywhere: the Advisor's rule engine, every scoring signal, and the
Graph's relationship computation are all deterministic and rule-based.

## Web UI

Visiting `/` in a browser serves the ROLE OS dashboard: a single responsive
page built with plain HTML, CSS, and JavaScript (no frontend framework),
with four tabs.

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

### Advisor tab (Epic 2)

- **Workspace filter** — scopes the Daily Brief and recommendation list to one workspace.
- **Daily Brief** — a short, structured morning brief (top recommended
  projects, critical risks, blocked projects, near-completion projects,
  stale high-priority projects, capability reuse opportunities), from
  `/advisor/daily-brief`.
- **Recommendation cards** — each shows a priority indicator, estimated
  effort, expected impact, and the full explanation/evidence behind it, from
  `/advisor/recommendations`.
- **Dismiss / Mark completed buttons** — call the corresponding
  `/advisor/recommendations/{id}/dismiss` and `.../complete` endpoints and
  remove the card from view immediately.

### Knowledge Graph tab (Epic 3)

- **Interactive graph** — a hand-rolled SVG view (no external JS graph
  library, no CDN) showing Projects, Workspaces, Capabilities, and
  whatever else has been loaded or expanded into view.
- **Click a node** — opens a detail panel with its type, full data, and
  every relationship touching it.
- **Expand neighbors / Collapse to selection** — pull in a node's
  immediate neighbors from `/graph/neighbors/{id}`, or collapse the view
  back down to one node and its direct connections.
- **Search** — free-text node search via `/graph/search`.
- **Filters** — by node type, workspace, and relationship type, re-fetched
  from `/graph` with the matching query parameters.
- **Highlight toggles** — shortest path between two nodes you pick from
  the detail panel (`/graph/path`), all dependency edges
  (`DEPENDS_ON`/`UNBLOCKS`), or all capability edges
  (`IMPLEMENTS`/`USES`/`SHARES_CAPABILITY`).
- The visualization is entirely optional presentation over the standalone
  `/graph/*` API — every one of these interactions is just a fetch call,
  and the Graph Engine (`app/graph/engine.py`, `queries.py`) is fully
  usable and tested with zero dependency on this tab or on any browser.

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

### Advisor API (Epic 2 — new, namespaced under `/advisor`)

Entirely additive; introduces no change to any route above.

| Method | Path                                                       | Description |
|--------|-------------------------------------------------------------|--------------|
| GET    | `/advisor/recommendations?workspace=&project_id=&recommendation_type=&minimum_priority_score=&include_dismissed=` | List recommendations (filterable) |
| GET    | `/advisor/recommendations/{id}`                                | Get one recommendation |
| GET    | `/advisor/daily-brief?workspace=`                                | Structured Daily Brief |
| POST   | `/advisor/recommendations/{id}/dismiss`                            | Dismiss a recommendation (persists forever) |
| POST   | `/advisor/recommendations/{id}/complete`                             | Mark a recommendation completed (persists forever) |

`GET /advisor/recommendations` and `GET /advisor/daily-brief` both refresh
the recommendation engine for the requested scope before reading — so the
data is always current without a separate "generate" endpoint, the same
pattern Epic 1 uses for `GET /pi/projects/{id}/health`.

### Knowledge Graph API (Epic 3 — new, namespaced under `/graph`)

Entirely additive; introduces no change to any route above. The graph is
rebuilt fresh from the three existing databases on every request — there
is no dedicated graph database.

| Method | Path                                              | Description |
|--------|----------------------------------------------------|--------------|
| GET    | `/graph?node_type=&workspace=`                        | Full graph, optionally filtered |
| GET    | `/graph/project/{id}?depth=`                            | Subgraph centered on one Project |
| GET    | `/graph/node/{id}`                                        | One node plus every edge touching it |
| GET    | `/graph/neighbors/{id}?direction=&edge_type=&node_type=&depth=` | Filterable BFS neighbor lookup |
| GET    | `/graph/path?source=&target=&max_depth=`                    | Unweighted shortest path between two nodes |
| GET    | `/graph/impact/{id}?max_depth=`                                | Impact analysis: cascading traversal grouped by node type, plus live Advisor recommendations for every affected Project |
| GET    | `/graph/search?q=&node_type=&workspace=`                          | Free-text node search |
| GET    | `/graph/meta/types`                                                 | The fixed node type / relationship type vocabularies |

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

## AI Advisor domain (Epic 2)

The Advisor turns Project Intelligence data (health scores, TODOs,
deliverables, decisions, dependencies, capabilities) and recent knowledge
activity into concrete, explainable recommendations — without calling any
external AI API.

### How recommendations are generated

Eight independent, single-responsibility rules live under
`app/advisor/rules/`, each a pure function
`evaluate(project, context) -> list[RecommendationCandidate]`:

| Rule                          | Recommendation type(s) it can produce |
|--------------------------------|------------------------------------------|
| `stale_project.py`               | `update_stale_project` — any non-completed project inactive 30+ days |
| `inactive_high_priority.py`        | `review_risk` — a high/critical priority project inactive 7+ days (a much shorter fuse, since inactivity on important work is itself a risk) |
| `near_completion.py`                 | `continue_project` — active project ≥65% complete with ≤4 items left |
| `missing_deliverables.py`              | `finish_deliverable` — active project with 1-6 undelivered deliverables |
| `overdue_todos.py`                       | `resolve_todo` — 2+ open to-dos older than 14 days |
| `blocked_dependency.py`                    | `unblock_dependency` — depends on a project that's unhealthy or explicitly at-risk/blocked |
| `critical_health.py`                         | `review_risk` or `review_decision` — health score below 40; the type depends on which Health Score signal is weakest (unresolved decisions vs. anything else) |
| `capability_opportunity.py`                    | `reuse_capability` — another project already exposes a capability matching this project's tags/description |

`app/advisor/engine.py` runs every rule against every relevant project each
time recommendations are requested, refreshing each project's Health Score
first so cross-project checks (like `blocked_dependency`) always compare
against current data.

### How scoring works

`app/advisor/scoring.py` is a small, shared, dependency-free toolkit used
by every rule — the same weighted-signal-with-graceful-degradation pattern
as the Health Score engine (`app/projects/health/`):

- `priority_weight`, `staleness_score`, `completion_ratio`,
  `confidence_from_availability`, and `effort_from_count` are pure
  functions of real project data (priority, dates, item counts).
- `weighted_combine(signals, weights)` combines whichever signals a rule
  computed into one 0-100 `priority_score`, **renormalizing over the
  signals actually present** rather than treating a missing signal as
  zero — the same graceful-degradation principle used throughout ROLE OS.
- **No randomness anywhere.** Every number a rule produces is traceable
  back to specific project fields (dates, counts, statuses).

### Why recommendations are explainable

Every `Recommendation` carries `reason` (why it fired), `evidence` (the
specific data points that contributed — e.g. "2 missing deliverables", "1
dependent project", "no activity in 45 days"), `suggested_action` (what to
do), and `impact` (what happens if you do it) — see the worked example in
the Epic 2 spec (`SUPER FACIL` / "Finish the remaining 2 deliverables").
None of this is templated after the fact from a generic label: every field
is built directly from the same data the rule inspected to decide to fire.

### Duplicate prevention and persistence

Recommendations live in their own SQLite database
(`ROLE_OS_ADVISOR_DB_PATH`), separate from both the knowledge DB and the
Project Intelligence DB — the Advisor only ever *reads* those two, never
writes to them.

Recommendations are deduplicated by `(project_id, recommendation_type)`: a
new row is only inserted if no existing row for that key is still "live"
(`expires_at` in the future). This means dismissing or completing a
recommendation suppresses it from being regenerated for the rest of its
natural lifetime (its `dismissed`/`completed` state is never overwritten),
while an **expired** live window allows a fresh recommendation for that
project + type to be generated if the underlying condition still holds.
Nothing is ever deleted, so the table doubles as a full history/audit log.

### AI-ready architecture

`app/advisor/narrative.py` defines `AdvisorNarrativeProvider`, the seam for
a future LLM-backed provider:

```python
class AdvisorNarrativeProvider(Protocol):
    def generate_summary(self, candidate) -> str: ...
    def generate_reason(self, candidate) -> str: ...
    def generate_daily_brief(self, greeting_name, sections) -> str: ...
```

`DeterministicNarrativeProvider` is the only implementation in this Epic —
it builds every string from f-string templates over the rule engine's own
structured output, so it's fully reproducible and requires no network
access. A future LLM-backed provider could improve *wording* (rephrasing
the same reason/evidence more naturally) without touching the rule engine,
scoring, or persistence at all — the rules and scoring remain the source
of truth for *what* to recommend and *why*; a narrative provider only ever
affects *how it reads*. **This Epic does not call OpenAI, Claude, or any
external API.**

## Knowledge Graph domain (Epic 3)

The Knowledge Graph turns everything already in the other three domains
into one relationship graph. It is a **read/compute layer, not a fourth
database**: `app/graph/engine.py`'s `build_graph()` reads the Builder
database, the Project Intelligence database, and the Advisor database
every time it is called and assembles a fresh in-memory graph — nothing
about a project, card, capability, or recommendation is duplicated into a
new store.

### Node types (12)

`Project`, `KnowledgeCard`, `Person`, `Application`, `Vendor`,
`Capability`, `Workspace`, `Decision`, `Deliverable`, `Prompt`, `Asset`,
`Conversation`.

Every node has a stable, globally unique id of the form `<type>:<raw-id>`
(e.g. `project:1a2b3c`). Entity nodes referenced only by name — `Person`,
`Application`, `Vendor` — are deduplicated by a slugified version of the
name, so "Microsoft" mentioned across ten different conversations still
resolves to one node.

### Relationship types (12)

| Type | Meaning | Produced by |
|------|---------|-------------|
| `DEPENDS_ON` | Project depends on Project | `dependency_graph.py`, from the Project Intelligence `dependencies` table |
| `UNBLOCKS` | The reverse of `DEPENDS_ON` — precomputed so "what does finishing this unlock?" is a single hop | `dependency_graph.py` |
| `IMPLEMENTS` | Project exposes/implements a Capability | `capability_graph.py` |
| `USES` | Project consumes a Capability, or uses an Application/Vendor (aggregated from its linked conversations) | `capability_graph.py`, `application_graph.py`, `vendor_graph.py` |
| `SHARES_CAPABILITY` | Consumer Project <-> provider Project, precomputed convenience edge | `capability_graph.py` |
| `PROVIDES` | Vendor provides an Application — a deterministic co-occurrence signal (vendor and application mentioned together in the same card) | `vendor_graph.py` |
| `REFERENCES` | Project references its own Decision/Deliverable/Prompt/Asset; KnowledgeCard references an Asset (a mentioned file) | `project_graph.py`, `knowledge_graph.py` |
| `RELATED_TO` | Project <-> related Project; KnowledgeCard <-> KnowledgeCard via Milestone 3's `related_conversations` | `project_graph.py`, `knowledge_graph.py` |
| `BELONGS_TO` | Project belongs to a Workspace; KnowledgeCard belongs to a Project (when linked via `project.conversations`) | `project_graph.py`, `knowledge_graph.py` |
| `CREATED_BY` | Project created by/owned by a Person | `people_graph.py` |
| `MENTIONS` | KnowledgeCard mentions a Person/Application/Vendor | `people_graph.py`, `application_graph.py`, `vendor_graph.py` |
| `GENERATED_FROM` | KnowledgeCard was generated from a Conversation | `knowledge_graph.py` |

### How the graph is generated

`build_graph()` loads projects, workspaces, capabilities and their
consumers, and dependencies from the Project Intelligence database; every
knowledge card from the Builder database (via the new internal
`app.db.list_all_cards()` — not a new public endpoint); nothing eagerly
from the Advisor database (that's only queried on demand, during impact
analysis). Each of the seven `builders/*.py` modules contributes
`(nodes, edges)` from its own slice of that data; `engine.py` merges every
builder's nodes first, then every builder's edges, so an edge from one
builder pointing at a node contributed by a *different* builder (e.g.
`vendor_graph.py`'s `PROVIDES` edges pointing at `application_graph.py`'s
Application nodes) is never silently dropped.

### Impact analysis

`app/graph/queries.py`'s `impact_analysis(graph, node_id, max_depth=4)`
answers "if this changes, what's affected?" — it does a breadth-first
traversal outward (both directions) up to `max_depth` hops, groups every
reached node by type, and then looks up live Advisor recommendations for
every affected Project. This directly matches the Epic 3 example: *if ROLE
MASTER changes → which Projects are affected → which Assets → which
Conversations → which Capabilities → which Advisor recommendations exist
for them.*

### Query Engine

Besides the generic `neighbors()`/`shortest_path()`/`search_nodes()`
primitives, `queries.py` exposes named convenience functions matching the
Epic 3 example questions directly — `projects_related_to()`,
`capabilities_used_by()`, `applications_connected_to()`,
`conversations_mentioning()`, `people_involved_in()`,
`projects_blocked_by()`, and `projects_unlocked_by_finishing()`. All of
these are pure functions over an already-built `Graph`, so they're usable
headlessly (from tests, a script, or a future AI provider) with no
dependency on the API or dashboard.

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
| `ROLE_OS_ADVISOR_DB_PATH`         | `samples/role_os_sample/00_SYSTEM/role_os_advisor.db`           | AI Advisor recommendations database (dashboard-owned; schema created automatically on first use) |

To point the dashboard at a real ROLE Knowledge OS generated by the builder:

```bash
export ROLE_OS_DB_PATH="/path/to/ROLE_KNOWLEDGE_OS/00_SYSTEM/role_os.db"
```

All three databases are intentionally separate: the knowledge DB is
regenerated wholesale each time `builder.py` runs; the projects DB is
mutated incrementally through the `/pi/*` API; the advisor DB is written
only by the recommendation engine. None of the three is ever clobbered by
changes to another.

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
    advisor/                     # AI Advisor domain (Epic 2)
      engine.py                    # Orchestrator: runs rules, dedupes, persists, builds Daily Brief
      models.py                     # RuleContext, RecommendationCandidate, Recommendation, DailyBrief
      scoring.py                     # Shared, deterministic scoring toolkit (no randomness)
      narrative.py                    # AdvisorNarrativeProvider interface + deterministic default
      db.py                             # Advisor DB: schema, dedupe-aware insert, dismiss/complete
      rules/                              # Eight independent, single-responsibility rules
        stale_project.py, near_completion.py, blocked_dependency.py,
        critical_health.py, overdue_todos.py, missing_deliverables.py,
        inactive_high_priority.py, capability_opportunity.py
    graph/                        # Knowledge Graph domain (Epic 3)
      models.py                     # Node/Edge/Graph data structures + the 12 node/12 relationship types
      engine.py                      # build_graph(): reads all 3 DBs, merges every builder's output
      queries.py                      # neighbors/shortest_path/impact_analysis/search + named example queries
      api_models.py                    # Pydantic response schemas for /graph/*
      builders/                          # One pure build(...) -> (nodes, edges) function per relationship family
        project_graph.py, dependency_graph.py, capability_graph.py,
        knowledge_graph.py, people_graph.py, application_graph.py,
        vendor_graph.py
    routers/
      health.py, projects.py, search.py, knowledge.py   # Milestone 1 API (unchanged)
      ui.py                                                # Dashboard page + /ui/recent, /ui/timeline
      pi/                                                    # Project Intelligence routers, namespaced /pi
        workspaces.py, projects.py, collections.py,
        capabilities.py, dependencies.py, health.py
      advisor.py                                               # Advisor API, namespaced /advisor
      graph.py                                                  # Knowledge Graph API, namespaced /graph
    templates/
      index.html               # Dashboard page (Jinja2): Knowledge, Projects, Advisor, and Knowledge Graph tabs
    static/
      css/style.css             # Responsive layout, no framework
      js/app.js                  # Knowledge, Project Intelligence, Advisor, and Knowledge Graph tab JS
  tests/                    # API, UI, Health Score, Projects DB, Advisor, and Graph tests (pytest + TestClient)
  requirements.txt
```
