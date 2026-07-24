# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Added

- Sprint B1: ChatGPT Conversation Importer — a dashboard-owned pipeline for
  importing ChatGPT conversation exports without regenerating the whole
  Builder-generated knowledge base. **Additive only**: no existing
  endpoint, table, or UI behavior changed.
  - New `dashboard/app/imports/` package: `parser.py` (validates the
    export, normalizes each conversation — title, timestamps, message
    count, participant roles, content — ignoring individually malformed
    records without aborting the import), `db.py` (owns its own SQLite
    file, `role_os_imports.db`, with `imported_conversations` and
    `import_runs` tables, schema auto-created on first use, same pattern
    as Epic 1/2), `service.py` (`run_import()`: parse -> normalize ->
    deduplicate -> persist -> report; shared by both the API route and the
    CLI so they can't drift), `models.py` (pydantic schemas).
  - Deduplication: each conversation is fingerprinted by
    `id:<external_id>` when the export provides one, otherwise a
    deterministic `hash:<sha256>` of title/timestamps/content. Re-imports
    are classified `imported` / `updated` (content changed) / `skipped`
    (unchanged) / `invalid` (malformed record) — never silently
    duplicated.
  - New API: `POST /import/chatgpt` (multipart upload, returns a
    structured `ImportRun` summary), `GET /import/history`,
    `GET /import/conversations` — namespaced under `/import`, new
    `python-multipart` dependency for file upload support.
  - New CLI: `python scripts/import_chatgpt.py <path>`, following the
    `scripts/seed_alpha_demo.py` sys.path pattern, calling the same
    `run_import()` the API uses.
  - New UI: an "Import ChatGPT conversations" panel on the Knowledge page
    (file picker, Import button, loading state, success/error summary) —
    calls the existing `/import/chatgpt` endpoint only, no new backend
    surface introduced for it.
  - Explicitly out of scope for this sprint (by design): AI knowledge
    extraction, project/capability matching, Advisor recommendations, and
    Knowledge Graph linking for imported conversations — those remain the
    Builder's job.
  - 27 new tests across `dashboard/tests/test_import_parser.py`,
    `test_import_service.py`, `test_import_api.py`, and repo-level
    `tests/test_import_chatgpt_cli.py`; 253/253 passing repo-wide.

- Epic 4: ROLE OS Command Center — a full UX/UI redesign of the
  dashboard. **UI-only**: no API, database, or backend logic was touched;
  every view is built entirely on the existing Milestone 1 knowledge API,
  Epic 1 `/pi/*`, Epic 2 `/advisor/*`, and Epic 3 `/graph/*` endpoints.
  - New reusable design system under `dashboard/app/static/css/`:
    `colors.css` (every color as a custom property, including a palette
    entry per Knowledge Graph node type), `layout.css` (the app shell
    grid, page containers, responsive breakpoints), `components.css`
    (nav items, buttons, cards, badges, the health ring, the search
    dropdown, the graph detail panel), and `animations.css` (subtle
    fade/rise-in, hover lift, and health-ring transitions, respecting
    `prefers-reduced-motion`). `style.css` is now a four-line `@import`
    entry point — no inline styles anywhere in the generated markup
    except the health ring's live score gradient and each graph node's
    live type color, which are inherently per-instance runtime values.
  - Replaced the Milestone 2/3 tab-based page with a single-page Command
    Center shell: a persistent icon sidebar (Home, Projects, Knowledge,
    Advisor, Graph, Assets, Settings) and a header (global search,
    workspace selector, live date/time, quick actions), with a small
    hash-based client-side router (`#/home`, `#/projects`,
    `#/project/{id}`, `#/knowledge`, `#/advisor`, `#/graph`, `#/assets`,
    `#/settings`) swapping pages in and out of one `#view-root` — no new
    server route was added for any of these pages.
  - **Home**: Today's Focus (top 3 Advisor recommendations with project,
    health ring, priority, estimated effort, expected impact, suggested
    action, and an Open Project button), Workspace Overview (a card per
    workspace with healthy/warning/critical project counts), an animated
    Health Dashboard (Projects, Knowledge Cards, Advisor Recommendations,
    Graph Nodes, Graph Relationships, each counting up on load), Recent
    Activity (timeline, recent decisions, recent deliverables, recent
    conversations), a Knowledge Graph Preview (a small non-interactive
    render of the Project subgraph that opens the full Graph page on
    click), and a Quick Search box whose results are grouped into
    Projects / Knowledge Cards / People / Applications / Vendors / Assets
    — all six of which map directly onto existing Knowledge Graph node
    types, so grouping is one `/graph/search` call away with no new
    endpoint required.
  - **Project page**: redesigned into a three-column layout — left
    (health ring, status, workspace, priority, Advisor summary), center
    (overview, notes, recent decisions, open to-dos, deliverables), right
    (capabilities provided/consumed, dependencies both directions,
    related projects, the project's live Advisor recommendations, and a
    Knowledge Graph preview that jumps into the full Graph page focused
    on this project).
  - **Graph page**: promoted to a dedicated full-screen page with mouse
    wheel zoom and click-drag pan (via an SVG viewport transform) added
    on top of Epic 3's existing click / expand / collapse / search /
    filter-by-type-workspace-relationship / highlight-dependencies /
    highlight-capabilities interactions, plus a new impact-analysis
    action wired to `GET /graph/impact/{id}` with its own highlight
    color. The graph rendering code was refactored into a reusable
    `createGraphView()` factory so the same engine now powers the Home
    preview, the Project page preview, and the full Graph page.
  - **Advisor page**: Daily Brief at the top, recommendation cards
    grouped by workspace (each showing evidence, impact, estimated
    effort, and Dismiss/Mark completed actions) — the same
    `/advisor/daily-brief` and `/advisor/recommendations` endpoints as
    before.
  - **Assets** and **Settings** pages added to round out the sidebar:
    Assets lists every `Asset` graph node; Settings shows read-only
    system status from the existing `/health` endpoint.
  - Regression: `dashboard/tests/test_ui.py` and
    `test_advisor_api.py::test_dashboard_page_includes_advisor_tab` were
    updated to check for the new sidebar/router markup instead of the
    retired `data-tab="..."` panels (the old assertions were testing DOM
    structure the spec explicitly requires replacing, not backend
    behavior); every Builder, Knowledge, Project Intelligence, Advisor,
    and Knowledge Graph API test is unchanged and still passing. New
    tests confirm the sidebar, header, and all four design-system CSS
    files are served, and that app.js's router/views still call only the
    pre-existing API surface. 226/226 passing repo-wide.
  - Updated root `README.md` and `dashboard/README.md` with the Command
    Center UI description and a screenshots placeholder section.

- Epic 3: Knowledge Graph engine. ROLE OS gains a first-class,
  explainable relationship engine — not just a visualization — built on
  top of the existing Builder, Project Intelligence, and Advisor
  databases with **no data duplication**: the graph is recomputed from
  those three databases on every call, the same recompute-on-read pattern
  the Advisor (Epic 2) uses for recommendations.
  - New domain under `dashboard/app/graph/`:
    - `models.py` — dependency-free `Node`/`Edge`/`Graph` data structures.
      Exactly 12 node types (`Project`, `KnowledgeCard`, `Person`,
      `Application`, `Vendor`, `Capability`, `Workspace`, `Decision`,
      `Deliverable`, `Prompt`, `Asset`, `Conversation`) and exactly 12
      relationship types (`DEPENDS_ON`, `PROVIDES`, `USES`, `REFERENCES`,
      `RELATED_TO`, `BELONGS_TO`, `CREATED_BY`, `MENTIONS`,
      `GENERATED_FROM`, `UNBLOCKS`, `IMPLEMENTS`, `SHARES_CAPABILITY`).
    - `builders/` — one file per relationship family, each a pure
      `build(...) -> (nodes, edges)` function: `project_graph.py`
      (Projects, Workspaces, and a project's own Decisions/Deliverables/
      Prompts/Assets), `dependency_graph.py` (`DEPENDS_ON` + the
      precomputed reverse `UNBLOCKS`), `capability_graph.py`
      (`IMPLEMENTS`/`USES`/`SHARES_CAPABILITY`), `knowledge_graph.py`
      (KnowledgeCard/Conversation nodes, `GENERATED_FROM`, `RELATED_TO`
      via Milestone 3's `related_conversations`, `BELONGS_TO` a linked
      Project), `people_graph.py`, `application_graph.py`, and
      `vendor_graph.py` (Person/Application/Vendor nodes deduplicated by
      slugified name, `MENTIONS`, aggregated `USES`, and a deterministic
      co-occurrence-based `PROVIDES` from Vendor to Application).
    - `engine.py`: `build_graph()` reads the Builder DB
      (`app.db.list_all_cards`, a new internal-only function — no new
      public API endpoint), the Project Intelligence DB, and the Advisor
      DB, runs every builder, and merges the results into one `Graph`
      (all nodes added before any edges, so cross-builder edges are never
      dropped for referencing a node contributed by a different builder).
    - `queries.py`: the Query Engine — `neighbors()` (filterable BFS),
      `shortest_path()` (unweighted BFS pathfinding), `impact_analysis()`
      (cascading traversal grouped by node type, e.g. "if ROLE MASTER
      changes → which Projects/Assets/Conversations/Capabilities are
      affected, and which Advisor recommendations exist for them"),
      `search_nodes()`, and named convenience wrappers matching the Epic's
      example questions (`projects_related_to`, `capabilities_used_by`,
      `applications_connected_to`, `conversations_mentioning`,
      `people_involved_in`, `projects_blocked_by`,
      `projects_unlocked_by_finishing`). All pure functions over an
      already-built `Graph` — no I/O beyond an optional Advisor lookup, so
      any future AI provider can reason over the graph headlessly.
  - New Graph API, entirely additive and namespaced under `/graph`:
    `GET /graph` (optionally filtered by node_type/workspace),
    `GET /graph/project/{id}`, `GET /graph/node/{id}`,
    `GET /graph/neighbors/{id}` (direction/edge_type/node_type/depth
    filters), `GET /graph/path` (shortest path between two nodes),
    `GET /graph/impact/{id}` (impact analysis), `GET /graph/search`, and
    `GET /graph/meta/types` (the fixed node/relationship vocabularies, for
    the dashboard's filter dropdowns).
  - Dashboard UI: a new "Knowledge Graph" tab (plain HTML/CSS/JS, no
    frontend framework, no CDN dependency) with a hand-rolled SVG graph
    view, a click-to-open detail panel, expand/collapse neighbors, search,
    filters by node type/workspace/relationship, and highlight toggles for
    the shortest path, dependencies, and capabilities. The visualization
    is entirely optional presentation over the standalone `/graph/*` API —
    the Graph Engine works completely independently of it.
  - The four Milestone 1 API endpoints, the Milestone 2 UI, and the full
    Epic 1 `/pi/*` and Epic 2 `/advisor/*` APIs and UI are completely
    unchanged; only new, additive endpoints and UI elements were
    introduced.
  - 48 new tests: unit tests for the `Node`/`Edge`/`Graph` primitives and
    every builder, integration tests for `build_graph()` against real
    Project Intelligence and knowledge databases (including graceful
    degradation when the knowledge DB is missing), traversal/pathfinding/
    impact-analysis tests, API tests for every `/graph/*` endpoint, and
    dashboard/regression tests confirming every previous API and UI
    surface is unaffected. 225/225 passing repo-wide.
  - Updated `dashboard/README.md` and root `README.md` documenting node
    types, relationship types, graph generation, and impact analysis.

- Epic 2: explainable AI Advisor. ROLE OS analyzes Projects, Knowledge
  Cards, Capabilities, Dependencies, Health Scores, TODOs, Deliverables,
  and Decisions to recommend what to do next — deterministic by default,
  fully explainable, and requiring no external AI API.
  - New domain under `dashboard/app/advisor/`:
    - Eight independent, single-responsibility rules under `rules/`:
      `stale_project`, `near_completion`, `blocked_dependency`,
      `critical_health`, `overdue_todos`, `missing_deliverables`,
      `inactive_high_priority`, `capability_opportunity`. Each is a pure
      function `evaluate(project, context) -> list[RecommendationCandidate]`.
      `critical_health` dynamically picks `review_risk` or
      `review_decision` depending on which Health Score signal is weakest.
    - `scoring.py`: a shared, deterministic toolkit (priority weighting,
      staleness, completion ratio, confidence-from-availability,
      weighted-signal-combination with graceful renormalization over
      missing signals) used by every rule. No randomness anywhere.
    - `engine.py`: orchestrates all eight rules across every Project,
      refreshing each project's Health Score first so cross-project checks
      (e.g. `blocked_dependency`) always use current data; merges
      same-key candidates (even from two different rules) before
      persisting, so duplicates never reach the database.
    - `narrative.py`: `AdvisorNarrativeProvider` interface (AI-ready seam
      for a future LLM-backed implementation) plus
      `DeterministicNarrativeProvider`, the only implementation used in
      this Epic — builds every string from the rule engine's own
      structured output, no network calls, fully reproducible.
    - `db.py`: recommendations persisted in their own SQLite database
      (`ROLE_OS_ADVISOR_DB_PATH`), separate from both the knowledge DB and
      the Project Intelligence DB, which the Advisor only ever reads.
      Deduplicated by `(project_id, recommendation_type)`: a new row is
      only inserted if none is still "live" (unexpired); dismissed and
      completed rows keep their state forever and continue to suppress
      regeneration until they expire, at which point a fresh
      recommendation may be generated if the condition still holds.
  - Every `Recommendation` includes: `id`, `project_id`, `workspace`,
    `title`, `summary`, `recommendation_type`, `priority_score`,
    `confidence_score`, `reason`, `evidence`, `suggested_action`,
    `estimated_effort`, `impact`, `created_at`, `expires_at`, `dismissed`,
    `completed` — the `reason`/`evidence`/`impact` fields make every
    recommendation self-explaining.
  - New Advisor API, entirely additive and namespaced under `/advisor`:
    `GET /advisor/recommendations` (filterable by workspace, project_id,
    recommendation_type, minimum_priority_score, include_dismissed),
    `GET /advisor/recommendations/{id}`, `GET /advisor/daily-brief`,
    `POST /advisor/recommendations/{id}/dismiss`,
    `POST /advisor/recommendations/{id}/complete`.
  - Daily Brief: top 3 recommended projects, critical risks, blocked
    projects, near-completion projects, stale high-priority projects, and
    capability reuse opportunities, each with a short explanation.
  - Dashboard UI: a new "Advisor" tab (plain HTML/CSS/JS, no framework)
    with a workspace filter, the Daily Brief, and recommendation cards
    showing priority, estimated effort, impact, full evidence/explanation,
    and Dismiss/Mark completed buttons.
  - The four Milestone 1 API endpoints, the Milestone 2 UI, and the full
    Epic 1 `/pi/*` API and UI are completely unchanged; only new, additive
    endpoints and UI elements were introduced.
  - 65 new tests: unit tests for every rule and every scoring function,
    persistence/duplicate-prevention tests, engine-level tests (including
    cross-rule dedup and Daily Brief structure), API tests for every
    `/advisor/*` endpoint, and a regression test confirming every previous
    API and UI surface is unaffected. 177/177 passing repo-wide.
  - Updated `dashboard/README.md` and root `README.md` explaining rule
    generation, scoring, explainability, and the AI-ready narrative
    provider seam.

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
