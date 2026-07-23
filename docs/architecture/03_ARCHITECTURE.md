# 03 — Architecture

## Repository layout

```
ROLE_OS/
  builder/      # CLI tool: builds the ROLE Knowledge OS + SQLite DB from a ChatGPT export
  dashboard/    # FastAPI app: read-only API + web UI over the generated SQLite database(s)
  docs/         # Project documentation (this directory)
  tests/        # Repo-level / integration tests
  scripts/      # Utility and automation scripts (e.g. run_alpha.sh/.bat, seed_alpha_demo.py)
  samples/      # Sample ChatGPT export + generated output for local testing
```

## The two halves: Builder and Dashboard

**Builder** (`/builder`) is an offline CLI with no third-party
dependencies. It takes a ChatGPT conversations export and produces a
structured `ROLE_KNOWLEDGE_OS` folder plus a SQLite database
(`role_os.db`). It never runs as a service and the Dashboard never writes
to its output — the relationship is one-directional.

**Dashboard** (`/dashboard`) is a FastAPI app that reads the Builder's
SQLite database (read-only, from the dashboard's perspective) and layers
three additional domains on top, each in its own namespace and its own
database:

| Domain | Namespace | Database | Introduced |
|---|---|---|---|
| Knowledge API | `/`, `/search`, `/projects`, `/knowledge/{id}`, `/ui/*` | `ROLE_OS_DB_PATH` (Builder-generated, read-only) | Milestones 1–3 |
| Project Intelligence | `/pi/*` | `ROLE_OS_PROJECTS_DB_PATH` (dashboard-owned) | Epic 1 |
| AI Advisor | `/advisor/*` | `ROLE_OS_ADVISOR_DB_PATH` (dashboard-owned) | Epic 2 |
| Knowledge Graph | `/graph/*` | none — computed on demand from the three DBs above | Epic 3 |
| Command Center UI | served at `/`, hash-routed client-side | none — pure presentation over the above | Epic 4 |

All three persisted databases are intentionally separate and are each
owned by exactly one domain:

- the **knowledge DB** is regenerated wholesale each time `builder.py`
  runs,
- the **projects DB** is mutated incrementally through the `/pi/*` API,
- the **advisor DB** is written only by the recommendation engine.

None of the three is ever clobbered by changes to another.

## Dashboard internal layout

```
dashboard/app/
  main.py            # FastAPI app + router registration + static mount
  config.py          # Environment-based settings (db paths, static/template dirs)
  db.py              # Knowledge database access layer (Milestone 1)
  models.py          # Knowledge API Pydantic response models
  projects/          # Project Intelligence domain (Epic 1)
    db.py                # Projects DB: schema, workspaces, projects, capabilities, dependencies
    models.py             # Project Intelligence Pydantic schemas
    health/                # Modular Health Score engine — one signal per file
  advisor/           # AI Advisor domain (Epic 2)
    engine.py            # Orchestrator: runs rules, dedupes, persists, builds Daily Brief
    models.py             # RuleContext, RecommendationCandidate, Recommendation, DailyBrief
    scoring.py             # Shared, deterministic scoring toolkit (no randomness)
    narrative.py            # AdvisorNarrativeProvider interface + deterministic default
    db.py                    # Advisor DB: schema, dedupe-aware insert, dismiss/complete
    rules/                    # Eight independent, single-responsibility rules
  graph/             # Knowledge Graph domain (Epic 3)
    models.py             # Node/Edge/Graph + 12 node types / 12 relationship types
    engine.py              # build_graph(): reads all 3 DBs, merges every builder's output
    queries.py              # neighbors/shortest_path/impact_analysis/search + named queries
    api_models.py            # Pydantic response schemas for /graph/*
    builders/                 # One pure build(...) -> (nodes, edges) function per relationship family
  routers/
    health.py, projects.py, search.py, knowledge.py   # Milestone 1 API (unchanged since)
    ui.py                                               # Dashboard page + /ui/recent, /ui/timeline
    pi/                                                   # Project Intelligence routers
    advisor.py                                             # Advisor API
    graph.py                                                # Knowledge Graph API
  templates/index.html   # Command Center app shell (Jinja2): sidebar + header + #view-root
  static/
    css/   # style.css (4-line @import) + colors/layout/components/animations.css
    js/app.js   # Hash router + every view + createGraphView() factory
tests/                # API, UI, Health Score, Projects DB, Advisor, and Graph tests (pytest + TestClient)
```

## Data flow

```
ChatGPT export (.zip)
        │
        ▼
   builder/builder.py  ──▶  extractors/ pipeline (summary, decisions,
        │                   todos, prompts, entities, relationships)
        ▼
  ROLE_KNOWLEDGE_OS/ (folder tree + role_os.db)
        │
        ▼
 dashboard/app/db.py  (read-only knowledge access)
        │
        ├──▶ Knowledge API (/search, /projects, /knowledge/{id}, /ui/*)
        │
        ▼
 dashboard/app/projects/db.py  (Project Intelligence DB, independently mutated via /pi/*)
        │
        ├──▶ Health Score engine (app/projects/health/) — reads a project's own data
        │
        ▼
 dashboard/app/advisor/engine.py
        (reads: Builder DB read-only, Project Intelligence DB read-only,
         writes: Advisor DB only)
        │
        ▼
 dashboard/app/graph/engine.py::build_graph()
        (reads: Builder DB, Project Intelligence DB, and — on demand,
         during impact analysis only — the Advisor DB; writes: nothing,
         nothing is persisted)
        │
        ▼
 Command Center UI (templates/index.html + static/js/app.js)
        (reads: every API above via fetch; writes: nothing directly —
         all writes go through the existing /pi/* and /advisor/* endpoints)
```

## Why the Knowledge Graph has no database of its own

`build_graph()` is called fresh on every `/graph/*` request. It loads
projects, workspaces, capabilities, and dependencies from the Project
Intelligence database; every knowledge card from the Builder database
(via the internal `app.db.list_all_cards()`, not a public endpoint);
and, only during impact analysis, live Advisor recommendations. Each of
the seven `builders/*.py` modules contributes `(nodes, edges)` from its
own slice of that data. `engine.py` merges every builder's **nodes**
first, then every builder's **edges**, so an edge from one builder
pointing at a node contributed by a different builder (e.g.
`vendor_graph.py`'s `PROVIDES` edges pointing at `application_graph.py`'s
Application nodes) is never silently dropped.

This is the same "recompute on read" pattern the Advisor uses for
recommendations — see [[02_PRINCIPLES]] §2.

## Where to go next

- [[04_DATA_MODEL]] — the concrete schemas and entities behind each domain.
- [[05_UI_GUIDELINES]] — how the Command Center is structured and styled.
- [[06_DEVELOPMENT_RULES]] — how to extend this architecture correctly.
