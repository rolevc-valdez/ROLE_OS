# Changelog

All notable changes to this project are documented in this file.

## [1.1.0] - 2026-07-30

### Added

- ROLE OS Dashboard MVP: Daily Session — the first functional MVP of a
  personal-operating-system daily workflow, per the ROLE Ecosystem's
  `SYSTEM.md`/`PRODUCT_LIFECYCLE.md` Build stage. **Additive only**: one
  new domain, one new router, one new SQLite file, one new sidebar page;
  every existing endpoint, page, and database is unchanged.
  - New `dashboard/app/session/` domain: `modes.py` (the single reusable
    source of truth for the six operation modes — PLAN, BUILD, CREATE,
    LAUNCH, OPERATE, LEARN — each with a name, purpose, expected AI
    behavior, and primary ROLE Ecosystem resources), `db.py` (SQLite
    persistence for sessions and a local project registry, following the
    exact same idempotent-schema/seed pattern as `app/projects/db.py`),
    `models.py` (Pydantic schemas), `markdown.py` (pure-function
    generation of the Claude session-initialization prompt and the
    Obsidian-compatible daily Markdown record — no AI/LLM call anywhere),
    and `decisions_adapter.py` (an adapter that reads the ROLE Ecosystem's
    own `DECISION_LOG.md` live when `ROLE_OS_ECOSYSTEM_DECISION_LOG_PATH`
    is configured, falling back to a small, explicitly-labeled snapshot
    otherwise — never duplicates the full log).
  - New `dashboard/app/routers/session.py`, namespaced under `/session`:
    `GET /session/modes`; `GET`/`PATCH /session/registry[/{id}]`; `GET
    /session/current`, `GET /session/recent`, `GET /session/{id}`, `POST
    /session/start` (409 if a session is already active), `POST
    /session/{id}/complete`; `GET /session/{id}/prompt`, `GET
    /session/{id}/markdown`, `GET /session/{id}/markdown/download`, `POST
    /session/{id}/save-to-vault` (writes the record into an optional,
    never-hardcoded `ROLE_OS_OBSIDIAN_DAILY_NOTES_DIR`), `GET
    /session/vault/config`; `GET /session/decisions/recent`.
  - Three new `Settings` fields (`app/config.py`): `session_db_path`
    (`ROLE_OS_SESSION_DB_PATH`, defaulting under the git-ignored `var/`
    directory rather than `samples/`, since session data is real personal
    data, not a checked-in fixture), `obsidian_daily_notes_dir`
    (`ROLE_OS_OBSIDIAN_DAILY_NOTES_DIR`, empty by default), and
    `ecosystem_decision_log_path` (`ROLE_OS_ECOSYSTEM_DECISION_LOG_PATH`,
    empty by default).
  - New sidebar page, **Session** (`#/session`), in
    `dashboard/app/static/js/app.js`: shows today's date, mode, project,
    objective, expected result, and session status (Not Started / Active
    / Completed) at a glance; a Start My Day form; the copyable Claude
    prompt once a session is active; an End My Day form; the generated
    Markdown record (copy, download, or optional save-to-vault) once
    completed; the local project registry (seeded with ROLE OS, ROLE
    ECOSYSTEM, ROLE MASTER, ROLE Commerce Factory, Brand Character OS,
    RoleValdez, and SUPER FACIL, editable inline); and Recent ecosystem
    decisions. Built as its own page rather than folded into the existing
    Home page, per the same reasoning as the Sprint 7 Dashboard decision
    (see `docs/product/DECISIONS.md`) — different data, different
    question, no natural shared layout.
  - Light-theme support added to `app/static/css/colors.css` via a
    `@media (prefers-color-scheme: light)` override block, purely
    additive: every existing rule already reads color exclusively through
    the custom properties that block redefines, so this alone re-themes
    the entire Command Center for a light OS preference, not just the new
    Session page.
  - 48 new tests: `test_session_db.py`, `test_session_markdown.py`,
    `test_session_decisions_adapter.py`, `test_session_api.py`,
    `test_session_ui.py`. Full suite: 464 passed, 0 failed.

## [1.0.0] - 2026-07-28

ROLE OS v1.0 release. See [`RELEASE_NOTES_v1.0.md`](RELEASE_NOTES_v1.0.md)
for the release-facing summary of highlights, known limitations, and
roadmap.

### Added

- Sprint 9: Release — the v1.0 release package. **Documentation only**: no
  code, API, database, or UI behavior changed except the version string
  itself.
  - New root-level release docs: `QUICK_START.md`, `INSTALLATION.md`,
    `ARCHITECTURE.md`, `RELEASE_NOTES_v1.0.md`, `LICENSE.md`,
    `FINAL_RELEASE_CHECKLIST.md`, `CONTRIBUTING.md`.
  - `README.md` reorganized with explicit Features, Architecture overview,
    Requirements, Running locally, Repository structure, and License
    sections (content already accurate elsewhere in the repo, now
    consolidated in one place).
  - `dashboard/README.md` updated to document the Settings domain
    (Sprint 8), which had shipped in code but was undocumented: the
    Settings page description, the `/settings/*` API table and response
    shape, a "Settings domain (Sprint 8)" narrative section, the
    Advisor Search default-limit change, and project-layout tree entries
    for every router/domain package that had been added since Epic 3
    (`imports/`, `extraction/`, `conversation_graph/`, `advisor_search.py`,
    `settings.py`) but was missing from that tree.
  - App version bumped from `1.0.0-alpha` to `1.0.0`
    (`dashboard/app/config.py`, `pyproject.toml`).

- Sprint 8: Settings — a Settings page backed by a real API, replacing the
  earlier placeholder that only read `/health`. **Additive only**: one new
  router, two new `Settings` fields, one default-value change to an
  existing endpoint; every other endpoint and page is unchanged.
  - Two new fields on `app/config.py`'s `Settings`: `license` (fixed
    `"Proprietary"`, matching `pyproject.toml`), `repo_root` (for git
    commit lookup), `default_import_path`
    (`ROLE_OS_DEFAULT_IMPORT_PATH`, informational only — nothing pre-fills
    an import dialog with it yet), and `search_result_limit`
    (`ROLE_OS_SEARCH_RESULT_LIMIT`, default 100).
  - `GET /advisor/search`'s `limit` query param now defaults to
    `Settings.search_result_limit` instead of a value hardcoded in the
    endpoint signature; passing `limit` explicitly still overrides it.
  - New `dashboard/app/routers/settings.py`, namespaced under `/settings`:
    `GET /settings` (general config, system status, about info,
    maintenance status in one response), `GET /settings/export` (download
    current settings as JSON), `POST /settings/import` (validate an
    uploaded configuration file and preview which `ROLE_OS_*` environment
    variables it maps to — never applies it to the running process, since
    there is no mechanism to safely mutate a live server's environment),
    `POST /settings/maintenance/rebuild-graph` (force a fresh
    `build_graph()` call and report node/edge counts), `POST
    /settings/maintenance/clear-cache` (clear the in-memory
    `get_settings()` `@lru_cache`).
  - Settings page (`dashboard/app/static/js/app.js`) rewritten to consume
    the new API: General/System status/About tables, an Export button, an
    Import-and-preview form, and Rebuild graph/Clear cache actions with
    their own status panel — replacing the old four-row `/health`-only
    table.
  - 16 new tests: `dashboard/tests/test_settings_api.py` (overview shape,
    export, import preview/validation/never-applies, maintenance actions,
    regression check that other endpoints are unaffected),
    `test_settings_ui.py` (nav/route/markup/endpoint-wiring regression
    checks), plus 2 new tests in `test_advisor_search_api.py` covering the
    new default-limit behavior. 386/386 passing repo-wide.

- Sprint 7: Dashboard — a new executive-summary sidebar page over the
  Importer/Explorer/Extraction/Knowledge Graph/Advisor Search pipeline.
  **Additive only, UI-first**: one new nav item/route, two thin new
  endpoints; zero new storage, zero new client- or server-side
  calculation beyond "most recent N" queries, zero changes to Home or any
  other existing page's content.
  - New API on the existing Extraction router (`routers/extraction.py`,
    zero changes to its existing endpoints): `GET /extraction/recent?limit=`
    (most recently extracted objects across every conversation, reusing
    the already-written `search_objects()` unfiltered) and `GET
    /extraction/runs?limit=` (most recent extraction runs across every
    conversation — the extraction-domain analogue of the already-existing
    `GET /import/history`). Backed by two additive functions in
    `app/extraction/db.py`: `_row_to_run()`, `list_recent_runs()`.
  - New **Dashboard** page (`dashboard/app/templates/index.html`,
    `dashboard/app/static/js/app.js`): sidebar nav item placed right after
    Home, route `#/dashboard`. Ten summary cards (Conversations, Projects,
    People, Tasks, Decisions, Ideas, Documents, Assets, Graph Nodes, Graph
    Edges) read verbatim from the existing `GET /import/metrics` — no
    field is recomputed, only displayed (reusing the same
    `health-dashboard-grid` + `animateCount()` pattern Home and the
    Explorer already use). Recent Activity (`GET /import/conversations`
    + the new `GET /extraction/recent`). System Status (`GET
    /import/history` for last import, the new `GET /extraction/runs` for
    last extraction, the same `graph_nodes`/`graph_edges` fields already
    in `/import/metrics` for graph status, and "Connected" once every
    other panel's fetch succeeds for database status — no separate
    health-check endpoint was added). Quick Actions: four buttons that
    just call `navigate()` to Knowledge (where the import panel lives),
    Explorer, Knowledge Graph, and Advisor (where Search Knowledge lives)
    — no new pages behind them. Loading/empty/error states throughout,
    matching the pattern already established by the Explorer and
    Knowledge Graph pages. Zero new CSS — every element reuses existing
    classes.
  - 17 new tests: `dashboard/tests/test_extraction_dashboard_endpoints.py`
    (ordering, limit, empty state for the two new endpoints),
    `test_dashboard_ui.py` (nav/route/metrics-mapping/quick-actions/
    empty-state/error-state regression checks, plus a check that Home and
    every other existing page's render function is still present
    unchanged). 400/400 passing repo-wide.

- Sprint 6: Advisor Search — keyword/partial-match search over imported
  conversations and extracted knowledge objects, surfaced as a new
  "Search Knowledge" section on the existing Advisor page. **Additive
  only**: two new files inside the existing `app/advisor/` package, a
  new router, a new UI section — every Epic 2 recommendation-engine file
  (`db.py`, `engine.py`, `rules/`, `scoring.py`, `narrative.py`,
  `routers/advisor.py`) and every existing `/advisor/*` route is
  byte-for-byte untouched.
  - New `dashboard/app/advisor/search.py` (`search(q, result_type, limit)`:
    unifies two existing, already-tested search paths — `app.imports.db
    .list_conversations_page(q=...)` for conversation matches (title,
    message content, source, id) and a new `app.extraction.db
    .search_objects(q=..., object_type=...)` helper for extracted-object
    matches — into one result list sorted by date. `get_object_result()`/
    `get_conversation_result()` back the two lookup endpoints. New
    `dashboard/app/advisor/search_models.py` (`SearchResult`,
    `SearchResponse` — `object_type`, `name`, `conversation_id`,
    `conversation_title`, `date`, `confidence` (`null` for conversations),
    `graph_node_id`).
  - New API on `/advisor/search`, registered via a **separate router**
    (`dashboard/app/routers/advisor_search.py`) from Epic 2's
    `routers/advisor.py`, so this sprint carries zero risk to the
    existing router: `GET /advisor/search?q=&type=&limit=`,
    `GET /advisor/search/objects/{id}`, `GET
    /advisor/search/conversations/{id}`. `type` must be one of
    `Conversation`/`Project`/`Person`/`Task`/`Decision`/`Idea`/`Document`/
    `Asset` or the request 400s. `graph_node_id` in every result matches
    the Sprint 5 Knowledge Graph's node id format exactly
    (`GET /conversation-graph/nodes/{id}`), so "Open Graph" needs no
    translation.
  - Advisor page (`dashboard/app/static/js/app.js`): a new "Search
    Knowledge" section at the top (search box, live/debounced ~250ms;
    type-filter `<select>`; Clear button; scrollable result list with
    *Open Conversation* / *Open Graph* actions per result) inserted above
    the existing Daily Brief/recommendations UI, which is otherwise
    unchanged. *Open Conversation* reuses the same
    `pendingExplorerConversationFocus` handoff the Knowledge Graph page
    introduced in Sprint 5; *Open Graph* navigates to
    `#/conversation-graph/{conversation_id}`. One new CSS rule
    (`.advisor-search-results { max-height: 420px; overflow-y: auto; }`
    in `components.css`) for the scrollable results container — no other
    new styling, everything else reuses existing card/badge/button
    classes.
  - 35 new tests: `dashboard/tests/test_advisor_search.py` (keyword
    search, partial matching, "show all X", type filters, result shape,
    conversation/object lookup), `test_advisor_search_api.py` (full API
    surface, invalid-type 400, a search result's `graph_node_id`
    resolving against `/conversation-graph/nodes/{id}`, and a regression
    check that `/advisor/recommendations`/`/advisor/daily-brief` are
    unaffected), `test_advisor_search_ui.py` (nav/route/cross-link
    regression checks). 383/383 passing repo-wide.

- Sprint 5: Knowledge Graph — a second, independent graph visualizing
  imported conversations connected to the knowledge objects extracted
  from them. **Additive only**: new domain, new API namespace, new UI
  page; extends (does not replace) the Explorer's conversation detail
  view and `GET /import/metrics`. Deliberately kept separate from the
  Epic 3 Knowledge Graph rather than merged into it — see below and
  [[DECISIONS]] for why.
  - New `dashboard/app/conversation_graph/` package: `models.py` (`Node`/
    `Edge`/`Graph`, 8 lowercase node types — `conversation`, `project`,
    `person`, `task`, `decision`, `idea`, `document`, `asset` — and
    exactly one relationship type, `contains`; edges deduplicated by
    `(source, target, type)`, edges referencing a missing node silently
    dropped), `engine.py` (`build_graph()`: one node per imported
    conversation + one node per extracted object + a `contains` edge from
    each conversation to every object extracted from it, computed fresh
    from the imports/extraction databases on every call — no new
    persisted store). One additive helper added to the frozen Sprint 4
    extraction module: `app.extraction.db.list_all_objects()` (read-only,
    used only by the graph engine).
  - New API on `/conversation-graph`: `GET /conversation-graph?conversation_id=&node_type=`
    (structured `{nodes, edges, metrics}` response), `GET
    /conversation-graph/nodes/{id}`, `GET
    /conversation-graph/nodes/{id}/neighbors`.
  - Why a second graph instead of extending Epic 3's `/graph`:
    `dashboard/tests/test_graph_api.py` hard-asserts exactly 12 node
    types / 12 relationship types via `/graph/meta/types`, and three
    architecture docs document that "12/12" as fixed. This sprint's types
    (`task`, `idea`, `document`, `contains`) aren't in that vocabulary,
    and this sprint's same-named types (`conversation`, `person`,
    `project`, `decision`, `asset`) come from an entirely different
    pipeline (imports/extraction, not Builder/PI/Advisor) — merging risked
    both breaking a passing test and silent node-id collisions across two
    unrelated data sources. A second, small, independent graph avoids
    both, at the cost of not being one unified graph.
  - New **Knowledge Graph** page: sidebar nav item + `#/conversation-graph`
    route (`dashboard/app/templates/index.html`,
    `dashboard/app/static/js/app.js`). Reuses the existing
    `createGraphView()` SVG zoom/pan/reset engine and
    `.graph-page`/`.graph-toolbar`/`.graph-detail-panel` CSS as-is; only
    new CSS is 3 additional node colors (`--node-task`, `--node-idea`,
    `--node-document` in `colors.css`) and a small `#kg-loading-msg`/
    `#kg-empty-msg` overlay-centering rule in `layout.css`, scoped to this
    page's own ids so the Epic 3 Graph page's markup/CSS is untouched.
    Filters: conversation, node type, Clear filters — exactly the two
    filters in scope. Two-way navigation with the Conversation Explorer:
    a "View in Knowledge Graph" button in the conversation detail overlay,
    and an "Open in Conversation Explorer" action in the graph's node
    detail panel.
  - `GET /import/metrics` (Explorer dashboard metrics) gains
    `graph_nodes`/`graph_edges`, real counts from `build_graph()`.
  - 32 new tests: `dashboard/tests/test_conversation_graph_engine.py`
    (node/edge validation, dedup, full graph construction, empty/
    orphaned/incomplete data), `test_conversation_graph_api.py` (full API
    surface, filters, node detail, neighbors, dashboard metrics),
    `test_conversation_graph_ui.py` (nav/route/cross-link regression
    checks, same string-assertion style as `test_ui.py`). 348/348 passing
    repo-wide.

- Sprint 4: Knowledge Extraction — deterministic, rule-based extraction of
  structured objects from imported conversations. **Additive only**: new
  domain, new database, new API namespace; extends (does not replace) the
  Explorer's conversation detail view and `GET /import/metrics`.
  - New `dashboard/app/extraction/` package: `rules.py` (pattern-based
    extractors for exactly seven object types — Project, Person, Task,
    Decision, Idea, Document, Asset — regex/keyword-line matching only, no
    AI/LLM call, styled after `builder/extractors/` but self-contained,
    not imported from it), `db.py` (owns its own SQLite file,
    `role_os_extraction.db`, with `extracted_objects` and
    `extraction_runs` tables, schema auto-created on first use), and
    `service.py` (`run_extraction()`: read a conversation from the
    imports domain -> run every extractor -> deduplicate -> persist ->
    report).
  - Deduplication mirrors the importer's own fingerprint strategy, scoped
    per-conversation: `sha256(conversation_id | object_type | normalized_title)`.
    Re-running extraction never duplicates — new candidates are inserted
    (`created`), changed ones updated in place (`updated`), unchanged ones
    just get `updated_at` bumped (`unchanged`). Objects removed via
    `DELETE /extraction/objects/{id}` are never silently recreated except
    by an explicit re-run finding the same match again.
  - New API on `/extraction`: `POST /extraction/conversations/{id}/run`
    (run/re-run, same idempotent endpoint), `GET
    /extraction/conversations/{id}/objects?object_type=`, `DELETE
    /extraction/objects/{object_id}`, `GET /extraction/metrics`.
  - `GET /import/metrics` (Sprint B1.5) now reads real counts from the
    extraction domain for `knowledge_objects` and all seven per-type
    fields (`projects`, `people`, `tasks`, `decisions`, `ideas`,
    `documents`, `assets` — the last two are new response fields);
    `pending_processing`/`processed` remain `0` (no per-conversation
    processing-state tracking yet, out of scope for this sprint).
  - Explorer conversation detail view (`dashboard/app/static/js/app.js`)
    gained a **Knowledge** section: an "Extract Knowledge" button and
    seven object-type lists (with confidence badge + per-object Delete),
    reusing existing `.activity-list`/`.badge`/`.link-btn`/`.page-section`
    styling — no new CSS classes were needed.
  - 32 new tests: `dashboard/tests/test_extraction_rules.py` (per-type
    extractor behavior), `test_extraction_service.py` (persistence, dedup,
    re-run, deletion+recreation), `test_extraction_api.py` (full API
    surface plus a regression check that `/import/*` and `/health` are
    unaffected). 316/316 passing repo-wide.

- Sprint B1.5: Conversation Explorer — browse, search, filter, inspect, and
  manage imported conversations. **Additive only**: extends Sprint B1's
  `/import/*` API and imports database; no existing endpoint, table, or UI
  page changed behavior.
  - `dashboard/app/imports/db.py`: two-column migration on the existing
    `imported_conversations` table (`status`, `import_run_id`), applied via
    idempotent `ALTER TABLE` wrapped in a duplicate-column guard so it's
    safe to run against a database created by Sprint B1 before this
    column existed. New `list_conversations_page()` (search/filter/sort/
    paginate, parameterized SQL), `get_conversation()` (full detail incl.
    content), `delete_conversation()`, `list_facets()`,
    `count_conversations()`. `service.run_import()` now generates the
    `import_run_id` up front and threads it through both
    `insert_conversation()`/`update_conversation()` and `record_run()` so
    every persisted conversation can be traced back to the run that
    produced its current state.
  - New API on the existing `/import` router: `GET /import/conversations`
    now accepts `page`/`page_size`/`sort_by`/`sort_dir`/`q`/`source`/
    `status`/`imported_after`/`imported_before` and returns a paginated
    envelope (`{items, total, page, page_size}`) instead of a bare list —
    the only contract change in this sprint, and one with no prior
    consumer (nothing was wired to the old shape yet). New
    `GET /import/conversations/{id}` (detail incl. content),
    `GET /import/conversations/{id}/export` (JSON file download),
    `DELETE /import/conversations/{id}`, `GET /import/facets` (distinct
    source/status values present, so filter dropdowns need no hard-coded
    provider list), `GET /import/metrics` (dashboard metrics — only
    `imported_conversations` is real; `pending_processing`, `processed`,
    `knowledge_objects`, `projects`, `decisions`, `assets` are `0` by
    design, since none of those pipelines exist yet).
  - New **Explorer** page: sidebar nav item + `#/explorer` route
    (`dashboard/app/templates/index.html`, `dashboard/app/static/js/app.js`).
    Reuses existing design-system pieces rather than introducing new ones
    where one already fit: the Home page's `health-dashboard-grid` +
    `animateCount()` for the metrics strip, the Graph page's
    `.graph-toolbar` for the filter bar, and the same shared
    `#detail-overlay`/`#detail-body` the Knowledge page's card detail
    already uses for the conversation detail view (message timeline with
    USER/ASSISTANT/SYSTEM color-coded via new minimal `.message-item`
    rules, search-within-conversation, metadata table, Copy/Export/Delete
    actions). New `.explorer-table`/`.explorer-pagination`/`.message-*`
    rules added to `components.css`, consistent with its existing
    per-feature section convention. Delete requires a native `confirm()`
    dialog.
  - 31 new tests: `dashboard/tests/test_explorer_api.py` (list/pagination/
    sort/search/filters/detail/export/delete/facets/metrics, all via
    `TestClient`) and `dashboard/tests/test_import_db.py` (pagination
    edge cases, sort-field whitelist fallback, migration idempotency).
    284/284 passing repo-wide.

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
