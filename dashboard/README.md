# ROLE OS Dashboard

FastAPI service over the SQLite knowledge base produced by the ROLE OS
Builder (`/builder`), a first-class **Project Intelligence** layer (Epic 1:
Workspaces, Projects, Capabilities, Dependencies, a Health Score engine),
an explainable **AI Advisor** (Epic 2) that recommends what to do next, and
— as of Epic 3 — a **Knowledge Graph** engine that turns all of the above
into one unified, queryable relationship graph. No external AI/LLM API is
called anywhere: the Advisor's rule engine, every scoring signal, and the
Graph's relationship computation are all deterministic and rule-based.

## Web UI — ROLE OS Command Center (Epic 4)

Visiting `/` in a browser serves the ROLE OS Command Center: a single-page
app shell built with plain HTML, CSS, and vanilla JavaScript (no frontend
framework, no build step). A persistent sidebar and header stay on screen
at all times; a small hash-based client-side router (`#/home`,
`#/projects`, `#/project/{id}`, `#/knowledge`, `#/explorer`, `#/advisor`,
`#/graph`, `#/conversation-graph`, `#/assets`, `#/settings`) swaps pages
in and out of one content area. This is a UI-only layer: every page below
is built entirely from the existing API described in the next section —
no new backend endpoint, database, or business logic was introduced for
Epic 4 (the Explorer page added in Sprint B1.5, the Knowledge Graph page
added in Sprint 5, and the Settings page's new backend added in Sprint 8
are the later exceptions — each is a UI-only consumer of its own API added
alongside it, not of Epic 4 itself).

### Design system

`app/static/css/` is a small reusable design system, imported in this
order by `style.css`:

- `colors.css` — every color as a CSS custom property (dark theme,
  status colors, priority colors, and one color per Knowledge Graph node
  type), so no other file hard-codes a hex value.
- `layout.css` — structural grid only: the app shell (sidebar + header +
  content), page containers, and responsive breakpoints.
- `components.css` — nav items, buttons, inputs, badges, cards, the
  health ring, the search dropdown, and the graph detail panel.
- `animations.css` — subtle transitions only (fade/rise-in on cards and
  sidebar items, a hover lift, health-ring transitions), and honors
  `prefers-reduced-motion`.

No inline styles are used in the generated markup, with two narrowly
scoped exceptions that are inherently per-instance runtime values: a
health ring's live conic-gradient percentage, and a graph node's live
type-based fill color.

### Sidebar navigation

Persistent icons for: **Home**, **Dashboard**, **Session**, **Projects**,
**Knowledge**, **Explorer**, **Advisor**, **Graph**, **Knowledge Graph**,
**Assets**, **Settings**.
("Graph" is the Epic 3 Knowledge Graph over Projects/Advisor/Builder data;
"Knowledge Graph" — added in Sprint 5 — is the separate, smaller graph over
imported conversations and their extracted objects. See
[Knowledge Graph domain (Sprint 5)](#knowledge-graph-domain-sprint-5)
below for why these are two independent features, not one. Similarly,
"Home" is Epic 4's original landing page over the Project Intelligence /
Advisor / Epic 3 Graph pipeline; "Dashboard" — added in Sprint 7 — is an
executive summary over the newer Importer / Explorer / Extraction /
Knowledge Graph / Advisor Search pipeline instead. Neither page's content
changed to make room for the other.)

### Home

- **Header**: global search (instant, grouped results), a workspace
  selector, a live date/time display, and quick actions (jump to the
  Daily Brief or the full Graph page).
- **Today's Focus** — the top 3 Advisor recommendations
  (`/advisor/recommendations`), each showing the project, its Health
  Score ring, priority, estimated effort, expected impact, suggested
  action, and an *Open Project* button.
- **Workspace Overview** — one card per workspace (`/pi/workspaces`)
  showing its projects split into healthy / warning / critical buckets
  by Health Score, computed client-side from `/pi/projects` (no per-
  project health recompute call — see Performance below).
- **Health Dashboard** — animated count-up indicators for Projects,
  Knowledge Cards, Advisor Recommendations, Graph Nodes, and Graph
  Relationships, sourced from `/pi/projects`, `/graph`, and
  `/advisor/recommendations`.
- **Recent Activity** — a timeline, recent decisions, recent
  deliverables, and recent conversations, from `/ui/timeline` and each
  project's own collections.
- **Knowledge Graph Preview** — a small, non-interactive render of the
  Project subgraph; clicking it opens the full Graph page.
- **Quick Search** — an instant search box whose results
  (`/graph/search`) are grouped by Projects, Knowledge Cards, People,
  Applications, Vendors, and Assets — the same six node types the
  Knowledge Graph already models, so no new grouping endpoint was needed.

### Dashboard page (Sprint 7)

An executive summary over the Importer/Explorer/Extraction/Knowledge
Graph/Advisor Search pipeline (Sprints B1-6) — deliberately separate from
Home above, which summarizes the older Project Intelligence/Advisor/Epic 3
Graph pipeline instead. Every number on this page is read directly from an
existing endpoint; nothing is recomputed client-side:

- **Summary cards** (`health-dashboard-grid`, same animated count-up
  pattern as Home's Health Dashboard and the Explorer's metrics strip):
  Conversations, Projects, People, Tasks, Decisions, Ideas, Documents,
  Assets, Graph Nodes, Graph Edges — all ten fields come straight out of
  the existing `GET /import/metrics` response (introduced in Sprint B1.5,
  filled in with real values across Sprints 4-5).
- **Quick Actions** — four buttons that just navigate: Import Conversation
  (→ Knowledge page, where the import panel lives), Conversation Explorer,
  Knowledge Graph, Search Knowledge (→ the Advisor page's search section).
- **Recent Activity** — Recent Conversations (`GET /import/conversations`,
  sorted by import date) and Recent Extracted Objects (`GET
  /extraction/recent`, a new thin endpoint — see below).
- **System Status** — Last import (`GET /import/history`), Last extraction
  (`GET /extraction/runs`, a new thin endpoint), Graph status (derived
  from the same `graph_nodes`/`graph_edges` already in `/import/metrics`),
  and Database status (`Connected` once every other panel's fetch has
  succeeded — if any fetch fails, the page shows an error instead, which
  *is* the "database unreachable" signal; no separate health-check call
  was added since the existing panels already require every database to
  be reachable).
- Loading, empty ("No conversations imported yet.", "Nothing extracted
  yet.", "No imports/extraction runs/graph data yet"), and error states
  are all handled explicitly, matching the pattern established by the
  Explorer and Knowledge Graph pages.

### Project page

Redesigned into a three-column layout:

- **Left** — Health Ring, Status, Workspace, Priority, and an Advisor
  Summary.
- **Center** — Overview, Notes, Recent Decisions, Open TODOs, and
  Deliverables.
- **Right** — Capabilities (provided/consumed), Dependencies (both
  directions), Related Projects, this project's live Advisor
  recommendations, and a Knowledge Graph Preview that opens the full
  Graph page focused on this project.

### Explorer page (Sprint B1.5 / Sprint 4)

A dedicated page for browsing, searching, filtering, and managing the
conversations the ChatGPT importer has persisted, and the knowledge
objects extracted from them — strictly an inspection and management view,
with no AI chat, graph, or advisor of its own:

- A metrics strip (reusing the Home page's `health-dashboard-grid` /
  `animateCount()` pattern): Imported Conversations, Pending Processing,
  Processed, Knowledge Objects, Projects, People, Tasks, Decisions, Ideas,
  Documents, Assets. The seven object-type counts plus Knowledge Objects
  are real (Sprint 4); Pending Processing/Processed stay `0` — there is no
  per-conversation processing-state tracking yet.
- A search/filter/sort toolbar: free-text search (title, message content,
  source, conversation id), source and status dropdowns populated from
  `GET /import/facets` (so a future provider like Claude or Gmail shows up
  automatically once something from it is imported, no redesign needed),
  an "imported today/this week/this month" preset, and a sort control
  (import date, conversation date, title, message count).
- A paginated table (`GET /import/conversations`) with View / Export /
  Delete actions per row.
- A **conversation detail** view reusing the same shared overlay as the
  Knowledge page's card detail (`#detail-overlay`): a chronological
  message timeline with USER/ASSISTANT/SYSTEM roles visually
  distinguished and per-message timestamps, a search-within-conversation
  box, a metadata panel (id, fingerprint, import run, dates, roles,
  source file, message count), Copy / Export JSON / Delete actions, and —
  as of Sprint 4 — a **Knowledge** section: an "Extract Knowledge" button
  (also used to re-run extraction) and seven subsections (Projects,
  People, Tasks, Decisions, Ideas, Documents, Assets) each listing that
  conversation's extracted objects with a confidence badge and a per-object
  Delete action. Message content is rendered exactly as imported — never
  summarized or modified; extracted objects are pattern-matched text, never
  generated.
- Delete requires an explicit confirm dialog and is irreversible.
- As of Sprint 5, the detail overlay's action row also has a **"View in
  Knowledge Graph"** button that navigates to the new Knowledge Graph page
  pre-filtered to that conversation; the Knowledge Graph page's node
  detail panel has a matching **"Open in Conversation Explorer"** action
  that comes back here and opens the same conversation.

### Graph page

Promoted to a dedicated full-screen page. Beyond Epic 3's click / expand /
collapse / search / filter (node type, workspace, relationship) /
highlight-dependencies / highlight-capabilities, it adds:

- **Zoom** (mouse wheel) and **pan** (click-drag), implemented as an SVG
  viewport transform.
- **Impact analysis** — a button wired to `GET /graph/impact/{id}`,
  highlighting every affected node in its own color and listing affected
  counts by type plus any live Advisor recommendations for affected
  projects.

The graph rendering code lives in one reusable `createGraphView()`
factory in `app.js`, shared by the Home preview, the Project page
preview, and this full page — so a bug fix or a new interaction only has
to be written once.

### Knowledge Graph page (Sprint 5)

A separate, smaller graph page over imported conversations and their
extracted knowledge objects — independent of the Graph page above (see
[Knowledge Graph domain (Sprint 5)](#knowledge-graph-domain-sprint-5) for
why). Reuses the same `createGraphView()` factory and `.graph-page`/
`.graph-toolbar`/`.graph-detail-panel` CSS as the Graph page, so it looks
and behaves consistently without any new rendering code:

- **Filters**: a conversation dropdown and a node-type dropdown (exactly
  the two filters this sprint supports), plus a Clear filters button.
  Nothing else — no search box, no relationship filter (there is only one
  relationship type), no saved views.
- **Zoom** (mouse wheel or +/- buttons), **pan** (click-drag), and
  **Reset view**.
- Clicking a node opens its detail panel: a Conversation node shows
  title/source/created/updated/message count; a knowledge-object node
  shows type/value/confidence/created/updated/source conversation. Either
  way, an action button crosses over to the Conversation Explorer for that
  conversation.
- Loading, empty ("No knowledge graph data yet...", shown when there are
  no conversations or none have been extracted yet), and error states are
  all handled explicitly.

### Advisor page

As of Sprint 6, opens with a **Search Knowledge** section: a single search
box (live, debounced), a type filter (`All` / Conversations / Projects /
People / Tasks / Decisions / Ideas / Documents / Assets), a Clear button,
and a scrollable result list — each result shows its type, name, source
conversation, date, confidence (when it has one), and *Open Conversation*
/ *Open Graph* actions. This is plain keyword/partial-match search over
already-stored data (`GET /advisor/search`) — no AI, no ranking beyond
recency. See [Advisor Search domain (Sprint 6)](#advisor-search-domain-sprint-6)
below for the full query semantics.

Below that, unchanged from Epic 2: Daily Brief (`/advisor/daily-brief`),
then recommendation cards grouped by workspace, each with evidence,
impact, estimated effort, and Dismiss / Mark completed actions
(`/advisor/recommendations`).

### Assets page

Lists every `Asset` node from the Knowledge Graph (`/graph?node_type=Asset`).

### Settings page (Sprint 8)

Reads the new `GET /settings` overview endpoint (see
[Settings domain (Sprint 8)](#settings-domain-sprint-8) below) instead of
the earlier placeholder that only showed `/health`:

- **General** — app name, version, default import path, search result
  limit, and every database's configured path.
- **System status** — total conversations, total extracted objects,
  database location, per-database file size, last import date, last
  extraction date.
- **About** — version, git commit (short hash, if the app is running from
  a git checkout), build date (always `null` — no build pipeline stamps
  one), license.
- **Export configuration** — downloads the current general/about settings
  as a JSON file (`GET /settings/export`).
- **Import configuration** — uploads a previously exported (or hand-written)
  JSON file and previews which environment variables it maps to
  (`POST /settings/import`); never applies anything to the running
  process — see below for why.
- **Maintenance** — "Rebuild graph" forces a fresh `build_graph()` call and
  reports the resulting node/edge counts (`POST
  /settings/maintenance/rebuild-graph`); "Clear cache" clears the
  in-memory `get_settings()` `@lru_cache` so an updated environment
  variable takes effect without a full process restart
  (`POST /settings/maintenance/clear-cache`).

### Performance

The Home page and project lists read each project's already-persisted
`health_score` field (from `/pi/projects`) rather than calling
`/pi/projects/{id}/health` once per project, so rendering a workspace
overview never fans out into N+1 requests. The Graph page only fetches
graph data when the user navigates to it or expands/searches within it —
nothing graph-related loads on Home beyond the one small preview subgraph
already needed for the preview panel.

### Screenshots

Screenshots aren't bundled in this repo yet. Run the Alpha demo (see the
root [`DEMO.md`](../DEMO.md)) and open `http://127.0.0.1:8000` to see the
live UI with seeded data.

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

### Advisor Search API (Sprint 6 — new, namespaced under `/advisor/search`)

Entirely additive; introduces no change to any route above, including
every existing `/advisor/*` route (a separate router — see
[Advisor Search domain (Sprint 6)](#advisor-search-domain-sprint-6) for
why). Keyword/partial-match search only — no NLP, no embeddings, no
semantic search, no AI/LLM call.

| Method | Path                                    | Description |
|--------|-------------------------------------------|--------------|
| GET    | `/advisor/search?q=&type=&limit=`           | Search conversations and/or extracted objects; `q` omitted lists everything of the selected `type` |
| GET    | `/advisor/search/objects/{object_id}`        | Look up one extracted-object result by id |
| GET    | `/advisor/search/conversations/{conversation_id}` | Look up one conversation result by id |

`type` must be one of `Conversation`, `Project`, `Person`, `Task`,
`Decision`, `Idea`, `Document`, `Asset`, or the request 400s.

`GET /advisor/search` response shape — every result carries enough to
render the required "Open Conversation" / "Open Graph" actions without a
second lookup:

```json
{
  "results": [
    {
      "object_type": "Decision",
      "name": "Use SSH for GitHub",
      "conversation_id": "…",
      "conversation_title": "Git Hardening",
      "date": "…",
      "confidence": 0.65,
      "graph_node_id": "decision:…"
    }
  ],
  "total": 1
}
```

`graph_node_id` is exactly the node id the Sprint 5 Knowledge Graph API
uses (`GET /conversation-graph/nodes/{id}`), so "Open Graph" needs no
translation step.

As of Sprint 8, an omitted `limit` defaults to `Settings.search_result_limit`
(itself defaulting to 100, overridable via `ROLE_OS_SEARCH_RESULT_LIMIT`)
instead of a value hardcoded in the query parameter; passing `limit`
explicitly still overrides it.

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

### ChatGPT Conversation Importer + Conversation Explorer API (Sprint B1 / B1.5 — new, namespaced under `/import`)

Entirely additive; introduces no change to any route above. Normalizes and
persists raw conversation metadata/content only — no AI knowledge
extraction, project matching, capability matching, advisor generation, or
graph inference happens here (that remains the Builder's job).

| Method | Path                  | Description |
|--------|------------------------|--------------|
| POST   | `/import/chatgpt`      | Upload a ChatGPT export file (`multipart/form-data`, field `file`); returns a structured import summary |
| GET    | `/import/history`      | Recent import runs, most recent first |
| GET    | `/import/conversations?page=&page_size=&sort_by=&sort_dir=&q=&source=&status=&imported_after=&imported_before=` | Search/filter/sort/paginate imported conversations (Sprint B1.5) |
| GET    | `/import/conversations/{id}`         | Full conversation detail, including content, for the Explorer's detail view |
| GET    | `/import/conversations/{id}/export`  | Download the full normalized conversation as a JSON file |
| DELETE | `/import/conversations/{id}`         | Delete an imported conversation |
| GET    | `/import/facets`                     | Distinct `source`/`status` values actually present, for building filter dropdowns without hard-coding provider names |
| GET    | `/import/metrics`                    | Explorer dashboard metrics (see below) |

`sort_by` accepts `imported_at` (default), `created_at`, `title`, or
`message_count`; `sort_dir` accepts `asc`/`desc`. `q` matches against title,
message content, source, and conversation id. `GET /import/conversations`
returns `{"items": [...], "total": N, "page": N, "page_size": N}` rather
than a bare list, so the Explorer can render page counts.

`GET /import/metrics` response shape — `imported_conversations`, the
seven knowledge-object counts (Sprint 4, read from the Extraction domain
below), and `graph_nodes`/`graph_edges` (Sprint 5, read from the Knowledge
Graph domain below) are real; `pending_processing`/`processed` stay `0`
on purpose — there is no per-conversation processing-state tracking yet,
only extraction counts in aggregate:

```json
{
  "imported_conversations": 42,
  "pending_processing": 0,
  "processed": 0,
  "knowledge_objects": 17,
  "projects": 2,
  "people": 5,
  "tasks": 4,
  "decisions": 3,
  "ideas": 1,
  "documents": 1,
  "assets": 1,
  "graph_nodes": 59,
  "graph_edges": 17
}
```

`POST /import/chatgpt` response shape:

```json
{
  "id": "…",
  "status": "completed",
  "source_filename": "conversations.json",
  "source_fingerprint": "…",
  "total_found": 100,
  "imported": 80,
  "updated": 5,
  "skipped": 12,
  "invalid": 3,
  "errors": [{"index": 42, "reason": "no id, title, or extractable content"}],
  "started_at": "…",
  "completed_at": "…"
}
```

### Settings API (Sprint 8 — new, namespaced under `/settings`)

Entirely additive; introduces no change to any route above. Aggregates
configuration and status information that already exists elsewhere in the
app (database paths, live counts, Knowledge Graph status, version/commit/
license) — no new persistence model, and no mechanism to mutate a running
process's environment.

| Method | Path                                    | Description |
|--------|-------------------------------------------|--------------|
| GET    | `/settings`                                 | General settings, system status, about info, and maintenance status in one response |
| GET    | `/settings/export`                           | Download the current general/about settings as a JSON file |
| POST   | `/settings/import`                            | Validate an uploaded configuration JSON file and preview which environment variables it maps to (never applies it) |
| POST   | `/settings/maintenance/rebuild-graph`           | Force a fresh `build_graph()` call (Epic 3 Knowledge Graph) and report node/edge counts |
| POST   | `/settings/maintenance/clear-cache`              | Clear the in-memory `get_settings()` cache |

`GET /settings` response shape:

```json
{
  "general": {
    "app_name": "ROLE OS",
    "app_version": "1.1.0",
    "database_paths": {"builder": "...", "projects": "...", "advisor": "...", "imports": "...", "extraction": "..."},
    "default_import_path": null,
    "search_result_limit": 100
  },
  "system": {
    "total_conversations": 0,
    "total_extracted_objects": 0,
    "database_location": "...",
    "database_sizes_bytes": {"builder": null, "projects": 86016, "advisor": 28672, "imports": 32768, "extraction": 36864},
    "last_import": null,
    "last_extraction": null
  },
  "about": {"version": "1.1.0", "commit": "e1dda55", "build_date": null, "license": "Proprietary"},
  "maintenance": {"cache_exists": true, "cache_description": "In-memory Settings cache (get_settings())"}
}
```

### Daily Session API (ROLE OS Dashboard MVP — new, namespaced under `/session`)

Entirely additive; introduces no change to any route above. Owns its own
SQLite file (`role_os_session.db`) for sessions and a small local project
registry. No AI/LLM call anywhere -- the Claude prompt and the Markdown
daily record are pure string templating over data the user entered.

| Method | Path                                    | Description |
|--------|-------------------------------------------|--------------|
| GET    | `/session/modes`                            | The six operation modes (PLAN/BUILD/CREATE/LAUNCH/OPERATE/LEARN), each with a purpose, expected AI behavior, and primary resources -- the single source of truth the UI reads instead of hardcoding a second copy |
| GET    | `/session/registry`                          | The local project registry (ROLE OS, ROLE ECOSYSTEM, ROLE MASTER, ROLE Commerce Factory, Brand Character OS, RoleValdez, SUPER FACIL, seeded by default) |
| PATCH  | `/session/registry/{id}`                     | Update a registry project's status/reference/milestone/next_action |
| GET    | `/session/current`                           | The currently active session, or `null` |
| GET    | `/session/recent`                            | Recently started sessions, most recent first |
| GET    | `/session/{id}`                              | A single session |
| POST   | `/session/start`                             | Start a new session (409 if one is already active) |
| POST   | `/session/{id}/complete`                     | Close a session: records completed work, decisions, blockers, next step |
| GET    | `/session/{id}/prompt`                       | The copyable Claude session-initialization prompt |
| GET    | `/session/{id}/markdown`                     | The Obsidian-compatible daily Markdown record, as JSON |
| GET    | `/session/{id}/markdown/download`            | The same record as a downloadable `.md` file |
| GET    | `/session/vault/config`                      | Whether an Obsidian Daily Notes folder is configured (`ROLE_OS_OBSIDIAN_DAILY_NOTES_DIR`) |
| POST   | `/session/{id}/save-to-vault`                | Optionally write the record directly into the configured vault folder |
| GET    | `/session/decisions/recent`                  | Recent ROLE Ecosystem decisions -- live from `role-ecosystem/DECISION_LOG.md` if `ROLE_OS_ECOSYSTEM_DECISION_LOG_PATH` is set and readable, otherwise a small documented fallback snapshot |

### Knowledge Extraction API (Sprint 4 — new, namespaced under `/extraction`)

Entirely additive; introduces no change to any route above. Rule-based
extraction only — no AI/LLM call, no summarization, no graph, no advisor,
no recommendations. Extracts and persists exactly seven object types:
Project, Person, Task, Decision, Idea, Document, Asset.

| Method | Path                                                  | Description |
|--------|--------------------------------------------------------|--------------|
| POST   | `/extraction/conversations/{id}/run`                    | Run (or re-run) extraction for one conversation; returns a structured run summary |
| GET    | `/extraction/conversations/{id}/objects?object_type=`   | List extracted objects for a conversation, optionally filtered to one type |
| DELETE | `/extraction/objects/{object_id}`                       | Delete one extracted object |
| GET    | `/extraction/metrics`                                   | Object counts by type (feeds `GET /import/metrics` above) |
| GET    | `/extraction/recent?limit=`                             | Most recently extracted objects across every conversation (Sprint 7, for the Dashboard's Recent Activity) |
| GET    | `/extraction/runs?limit=`                               | Most recent extraction runs across every conversation (Sprint 7; the extraction-domain analogue of `GET /import/history`) |

`POST /extraction/conversations/{id}/run` response shape — safe to call
repeatedly; see the Knowledge Extraction domain section below for the
dedup/re-run behavior:

```json
{
  "id": "…",
  "conversation_id": "…",
  "status": "completed",
  "total_found": 9,
  "created": 9,
  "updated": 0,
  "unchanged": 0,
  "counts_by_type": {"Project": 1, "Person": 2, "Task": 2, "Decision": 1, "Idea": 1, "Document": 1, "Asset": 1},
  "started_at": "…",
  "completed_at": "…"
}
```

Every extracted object carries: `conversation_id`, `source`, `confidence`
(0-1), `fingerprint`, `extraction_run_id`, `created_at`, `updated_at`.

### Knowledge Graph API (Sprint 5 — new, namespaced under `/conversation-graph`)

Entirely additive; introduces no change to any route above, including the
Epic 3 `/graph` API (a genuinely separate, independent graph — see
[Knowledge Graph domain (Sprint 5)](#knowledge-graph-domain-sprint-5)).
Computed fresh from the imports and extraction databases on every
request; no dedicated graph database.

| Method | Path                                              | Description |
|--------|-----------------------------------------------------|--------------|
| GET    | `/conversation-graph?conversation_id=&node_type=`     | Full graph, optionally filtered to one conversation's subgraph and/or one node type |
| GET    | `/conversation-graph/nodes/{id}`                        | One node plus every edge touching it |
| GET    | `/conversation-graph/nodes/{id}/neighbors`               | One-hop connected nodes, each paired with the connecting edge |

`GET /conversation-graph` response shape:

```json
{
  "nodes": [
    {"id": "conversation:123", "type": "conversation", "label": "Git Hardening", "data": {"...": "..."}},
    {"id": "decision:456", "type": "decision", "label": "Use SSH for GitHub", "data": {"confidence": 0.65, "conversation_id": "123", "...": "..."}}
  ],
  "edges": [
    {"source": "conversation:123", "target": "decision:456", "type": "contains"}
  ],
  "metrics": {"nodes": 2, "edges": 1}
}
```

`node_type` must be one of the 8 supported types (`conversation`,
`project`, `person`, `task`, `decision`, `idea`, `document`, `asset`) or
the request 400s. Filtering by `conversation_id` for an id that doesn't
exist in the graph (e.g. a deleted conversation) returns an empty graph,
not an error — see Known limitations below for why filtering and
deletion interact this way.

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

## ChatGPT Conversation Importer + Conversation Explorer domain (Sprint B1 / B1.5)

A lightweight, dashboard-owned importer for bringing ChatGPT conversations
into ROLE OS without regenerating the whole Builder-generated knowledge
base. It lives entirely under `app/imports/` (`parser.py`, `db.py`,
`service.py`, `models.py`) and owns its own SQLite file, same pattern as
Project Intelligence and the Advisor.

**What it does:** validates the export, normalizes each conversation
(source, external id, title, created/updated timestamps, message count,
participant roles, content, import timestamp, source file/fingerprint),
deduplicates, and persists — plus a run history record per import.

**What it intentionally does not do:** no summarization, tagging,
classification, project/capability matching, advisor generation, or graph
inference. Those all remain the Builder's job (`builder/knowledge_extractor.py`),
which this package never imports or calls.

### Supported input format

The ChatGPT export's `conversations.json` shape — a JSON array of
conversation objects, each with `id`, `title`, `create_time`, `update_time`,
and a `mapping` of node-id -> `{"message": {...}}` (same shape as
`samples/chatgpt_export_example/conversations-test.json`, and the format
`builder.py` already consumes). A malformed/non-JSON file, or a top-level
value that isn't a JSON array, fails the whole import with a clear error.
An individual malformed conversation record within an otherwise-valid file
is skipped and counted as `invalid` — it does not abort the rest of the
import.

### Deduplication behavior

Each normalized conversation gets a stable fingerprint: `id:<external_id>`
when the export provides one, otherwise a deterministic
`hash:<sha256 of title+timestamps+content>` fallback. On import:

- **no existing row for that fingerprint** -> inserted, counted `imported`
- **existing row, content changed** -> row updated in place, counted `updated`
- **existing row, content unchanged** -> left as-is (only `last_seen_at`
  bumped), counted `skipped`

Re-importing the same export file therefore never creates duplicate rows.

### How to run an import

- **UI** — Knowledge page, "Import ChatGPT conversations" panel: pick a
  file, click Import, see a live summary (imported/updated/skipped/invalid).
- **API** — `POST /import/chatgpt` (see [API endpoints](#api-endpoints) above).
- **CLI** — `python scripts/import_chatgpt.py <path-to-conversations.json>`,
  which calls the same `app.imports.service.run_import` the API route
  calls, so the two can never drift.

### Conversation Explorer (Sprint B1.5)

A browse/search/inspect/manage UI over what the importer persisted —
Explorer sidebar page, backed by additions to the same `/import/*` API
(`GET /import/conversations` now search/filter/sort/paginate, plus
`GET /import/conversations/{id}`, `GET /import/conversations/{id}/export`,
`DELETE /import/conversations/{id}`, `GET /import/facets`,
`GET /import/metrics`). See [Explorer page](#explorer-page-sprint-b15)
above for the UI walkthrough. Two behaviors worth calling out:

- **Search** matches title, message content, source, and conversation id
  in one query (`q=`) — a single search box, not per-field inputs.
- **Filters** are deliberately data-driven, not hard-coded: the Explorer
  asks `GET /import/facets` for the distinct `source`/`status` values that
  actually exist and builds its dropdowns from that, so a future provider
  (Claude, Gemini, Gmail, ...) appears as a filter option automatically
  the first time something from it is imported — no UI change required.

### Known limitations

- No background/continuous sync — every import is a one-shot, user-initiated run.
- The whole file is parsed into memory at once (no streaming parser); very
  large exports will use memory proportional to file size.
- Content-change detection is a fingerprint of the full normalized content,
  not a diff — an update replaces the whole stored conversation, it doesn't merge.
- Imported conversations are not (yet) linked to Project Intelligence
  projects, surfaced in the Knowledge Graph, or scored by the Advisor —
  that linkage is a natural next step, not part of this sprint.
- Explorer's `status` column only ever holds `"imported"` today — there is
  no processing pipeline yet, so the Status filter has exactly one option
  until a later sprint adds one.
- Explorer search matches with a plain SQL `LIKE` scan over the stored
  content — fine at the scale of a personal knowledge base, but not a full
  text index; it will not scale to a very large corpus.
- Delete is permanent (no undo/trash) — the confirm dialog is the only
  safety net.

## Knowledge Extraction domain (Sprint 4)

Extracts structured objects from imported conversations using
deterministic, rule-based pattern matching — regex and keyword-line
matching, the same style `builder/extractors/` already uses for the
Builder pipeline. Lives entirely under `app/extraction/` (`rules.py`,
`db.py`, `service.py`, `models.py`) and owns its own SQLite file, same
pattern as every other domain.

**Supported object types — exactly these seven, no more:**

| Type | How it's detected |
|------|---------------------|
| Project | Lines matching project/initiative keywords (`proyecto`, `project`, `iniciativa`, `lanzamiento de`, `launch of`) |
| Person | Capitalized two/three-word name sequences (e.g. "Maria Gonzalez"), with a small blocklist for common false positives |
| Task | Lines matching outstanding-work keywords (`pendiente`, `falta`, `to-do`, `task`, `hay que`, `necesitamos`) |
| Decision | Lines matching agreement/decision keywords (`decid`, `aprob`, `quedamos`, `vamos a usar`, `agreed`, `decision`) |
| Idea | Lines matching suggestion keywords (`idea`, `podríamos`, `what if`, `se me ocurre`, `propuesta`, `brainstorm`) |
| Document | Filenames with document extensions (pdf, doc(x), txt, md, csv, xls(x), ppt(x), json) |
| Asset | Filenames with media extensions (png, jpg(eg), webp, gif, svg, mp4, mov, mp3, wav, zip) |

Every extracted object is a verbatim snippet from the conversation (a
matched line, a detected name, a detected filename) — nothing is
rewritten, summarized, or generated. Each carries a `confidence` (0-1):
file-extension matches get a fixed 0.85 (exact match, high reliability);
keyword-line and name matches start around 0.55-0.6 and rise slightly with
repeated hits, capped at 0.9.

**What it intentionally does not do:** no AI/LLM call, no summarization,
no free-form generation, no additional object types, no graph inference,
no Advisor recommendations, no automatic Project Intelligence linking.

### Deduplication behavior

Same fingerprint strategy as the importer, applied per-conversation: each
candidate object is fingerprinted as
`sha256(conversation_id | object_type | normalized_title)`. Running
extraction on the same conversation again:

- **no existing row for that fingerprint** -> inserted, counted `created`
- **existing row, confidence changed** -> updated in place, counted `updated`
- **existing row, identical** -> left as-is (only `updated_at` bumped), counted `unchanged`

Objects from a previous run that no longer match are **not**
auto-deleted — deletion is always explicit, via
`DELETE /extraction/objects/{id}`. Re-running extraction is therefore
always safe: it never creates duplicates, and it never silently removes
something you kept.

### How to run extraction

- **UI** — open any conversation in the Explorer (or Knowledge page) and
  use the "Extract Knowledge" button in the conversation detail's
  Knowledge section; the same button re-runs extraction.
- **API** — `POST /extraction/conversations/{id}/run`.

### Known limitations

- Regex/keyword-based, not NLP — it will miss decisions/tasks/ideas
  phrased outside the known keyword patterns, and the Person detector can
  both miss real names (all-lowercase, single-word) and occasionally
  match a capitalized non-name phrase not already in the blocklist.
- No confidence threshold/filtering in the API or UI — every match above
  is persisted and shown, regardless of how low its confidence is.
- No cross-conversation deduplication — the same person or project
  mentioned in two different conversations is stored as two separate
  objects (fingerprinted per-conversation), not merged into one.
- No linkage yet to Project Intelligence projects, the Epic 3 Knowledge
  Graph, or the Advisor. (As of Sprint 5, extracted objects *are* linked
  into their own, separate Knowledge Graph — see below — but that's a
  `contains` edge back to the source conversation, not a link into PI,
  Epic 3's graph, or the Advisor.)

## Knowledge Graph domain (Sprint 5)

Displays and navigates the relationships between imported conversations
and the knowledge objects extracted from them. Lives entirely under
`app/conversation_graph/` (`models.py`, `engine.py`, `api_models.py`) and
is a **read/compute layer, not a new database** — same "no dedicated
graph database" approach as the Epic 3 Knowledge Graph, just applied to a
different, smaller pair of source databases (imports + extraction,
instead of Project Intelligence + Advisor + Builder).

**Why a second, separate graph instead of extending Epic 3's `/graph`?**
Epic 3's graph has a frozen, test-locked vocabulary of exactly 12 node
types and 12 relationship types (`GET /graph/meta/types` is asserted
against those exact counts), built from a completely different pipeline
(the Builder's `knowledge_cards`, Project Intelligence, and the Advisor).
This sprint's node types (`Task`, `Idea`, `Document`) and relationship
type (`contains`) don't exist in that vocabulary, and this sprint's
"Conversation"/"Person"/"Project"/"Decision"/"Asset" concepts come from an
entirely different pipeline (the imports/extraction domains) than Epic
3's same-named types. Extending Epic 3's tuples would both break an
existing passing test and risk silent node-id collisions between two
unrelated data sources sharing a type name. A second, independent,
much smaller graph avoids both problems and keeps Epic 3 completely
untouched. See [[DECISIONS]] for the full reasoning.

### Supported node types (8)

`conversation`, `project`, `person`, `task`, `decision`, `idea`,
`document`, `asset` — lowercase, a separate vocabulary from Epic 3's
12 (capitalized) types. Every node id is `<type>:<raw-id>`, e.g.
`conversation:4cf8e31f...` or `decision:754c61ec...`.

### Supported relationship type (1)

`contains` — every edge is `Conversation -> contains -> <object>`, one per
extracted knowledge object, generated directly from
`extracted_objects.conversation_id`. No relationships are inferred
between extracted objects themselves (no "Person works on Project", no
"Task belongs to Project", etc.) — v1.0 only represents relationships
already explicit in the stored data.

### How the graph is generated

`build_graph()` reads every imported conversation
(`app.imports.db.list_conversations()`) and every extracted object
(`app.extraction.db.list_all_objects()`, a new read-only helper added for
this sprint), turns each into a node, and adds one `contains` edge per
object back to its source conversation. Nodes are deduplicated by id;
edges are deduplicated by `(source, target, type)` so the same
conversation/object pair is never linked twice. An edge whose source or
target node doesn't exist is silently dropped rather than raised — this
is what makes an orphaned extracted object (its source conversation was
deleted) safe: the object still appears as a node, it just ends up with
no edge pointing to it.

### How to open and navigate the graph

- **UI** — sidebar → **Knowledge Graph** (`#/conversation-graph`), or from
  the Conversation Explorer's conversation detail, click **"View in
  Knowledge Graph"** to jump straight to that conversation's subgraph.
  Click any node for its detail panel; from a knowledge-object node's
  detail panel, **"Open in Conversation Explorer"** jumps back.
- **API** — `GET /conversation-graph` (see API endpoints above).

### Filters

Exactly two, per the v1.0 scope: **conversation** and **node type**. Both
are query params on the same `GET /conversation-graph` endpoint and can be
combined; a Clear filters control resets both. No free-text search, no
time-range analysis, no clustering, no saved views, no layout options —
deliberately out of scope for this sprint.

### Known limitations

- Only one relationship type (`contains`) — no inferred relationships
  between extracted objects (e.g. no "these two Decisions are related"),
  even where a human reader might see an obvious connection.
- No cross-conversation identity — the same person mentioned in two
  conversations produces two separate Person nodes, one per conversation
  (this graph reuses the extraction domain's per-conversation
  fingerprinting as-is; see Sprint 4's own "no cross-conversation
  deduplication" limitation above).
- The graph is recomputed from scratch on every request. Fine at the
  scale of a personal knowledge base; a very large number of
  conversations/objects would make every graph request proportionally
  slower (no caching layer).
- No multi-hop traversal, shortest-path, or impact-analysis queries (all
  present in Epic 3's `/graph`) — this sprint only supports one-hop
  "connected nodes," matching the simple star topology (a conversation and
  its directly contained objects) this vocabulary actually has.
- Layout is a simple circular arrangement (same `createGraphView()` layout
  used elsewhere) — there is no force-directed or hierarchical layout
  option.

## Advisor Search domain (Sprint 6)

Lets you find any imported conversation or extracted knowledge object by
keyword — plain, deterministic, case-insensitive substring matching, no
AI, no LLM, no NLP, no embeddings, no semantic search, no ranking beyond
recency. Lives in two new, additive files inside the existing
`app/advisor/` package (`search.py`, `search_models.py`) and a new router
(`routers/advisor_search.py`); the Epic 2 recommendation engine's own
files (`db.py`, `engine.py`, `rules/`, `scoring.py`, `narrative.py`,
`routers/advisor.py`) are completely untouched by this sprint.

**Why a new module inside `app/advisor/` instead of extending the
recommendation engine?** They answer two different questions — "what
should I work on next?" (Epic 2, rule-based scoring over Project
Intelligence data) vs. "where is everything about X?" (Sprint 6, keyword
search over imported conversations and extracted objects) — with
different data sources and no shared logic. Keeping them as sibling
modules under the same `/advisor` umbrella (not merged into one file, but
also not a separate top-level domain) reflects that they're both part of
"ask ROLE OS about your knowledge" without one having to accommodate the
other's very different internals. See [[DECISIONS]] for the full
reasoning.

### Supported query types

Every query is one call to `search(q, result_type)`:

- **Keyword search** — `q="GitHub"` matches conversation titles, message
  content, source, and id (reusing the Explorer's own
  `list_conversations_page(q=...)`), plus extracted-object titles
  (reusing a new `extraction.db.search_objects(q=...)` helper). Partial
  matches count — `q="Fresh"` matches "Freshservice".
- **"Show all X"** — an empty/omitted `q` with a `result_type` filter set
  lists everything of that type, unfiltered by keyword.
- **"Show everything related to X"** — an empty `result_type` with a `q`
  set searches across every conversation and every object type in one
  call, merged and sorted by date (most recent first).

There is no query language beyond `q` + `result_type` — no boolean
operators, no field-scoped search, no NLP parsing of the query text.

### How results are shaped

Every result (conversation or object) carries: `object_type`, `name`,
`conversation_id`, `conversation_title`, `date`, `confidence` (`null` for
conversations — only extracted objects have one), and `graph_node_id` —
the exact id the Sprint 5 Knowledge Graph API expects, so "Open Graph"
works with zero translation.

### How to search

- **UI** — sidebar → Advisor → **Search Knowledge** (at the top of the
  page, above the existing Daily Brief/recommendations): a search box
  (live, debounced ~250ms), a type filter, a Clear button, and a
  scrollable result list with *Open Conversation* (jumps to the
  Conversation Explorer, same `pendingExplorerConversationFocus` handoff
  the Knowledge Graph page already uses) and *Open Graph* (jumps to the
  Knowledge Graph page, pre-filtered to that result's conversation)
  actions on every result.
- **API** — `GET /advisor/search?q=&type=` (see API endpoints above).

### Known limitations

- Substring matching only — no fuzzy matching, no typo tolerance, no
  relevance ranking (results are sorted by date, not match quality).
- No pagination — results are capped at `limit` (default 100, max 500)
  and the UI relies on a scrollable container rather than paging through
  more.
- Object search matches title only, not full extracted content (there
  isn't any beyond the title/value already extracted) — this is a search
  over what Sprint 4 stored, not a search over raw conversation text for
  object-type results (conversation-type results do search full message
  content, via the Explorer's existing search).
- No saved searches, no search history, no query suggestions.

## Settings domain (Sprint 8)

Centralizes configuration and metadata that already exists elsewhere in
the app so it's visible and exportable in one place. Lives entirely in a
single `app/routers/settings.py` module — no new package, no new
database. Two small additions to `app/config.py` back it:
`default_import_path` (`ROLE_OS_DEFAULT_IMPORT_PATH`, purely informational
— nothing currently pre-fills an import dialog with it) and
`search_result_limit` (`ROLE_OS_SEARCH_RESULT_LIMIT`, which *is* wired in
as the Advisor Search API's default `limit`, see above).

### Why import can only validate and preview, never apply

`POST /settings/import` parses the uploaded file, maps every recognized
field to its environment variable name (`_ENV_VAR_MAP`), and returns that
mapping — it never writes to the process environment or restarts
anything. This is a deliberate boundary, not a missing feature: ROLE OS
has no mechanism (and this sprint adds none) to safely mutate a live
server's environment variables from an untrusted upload. The response
tells the caller exactly which `ROLE_OS_*` variable to set for each field
it recognized, so they can apply it themselves and restart.

### Why "Rebuild graph" and "Clear cache" are the only maintenance actions

The Epic 3 Knowledge Graph (`app/graph/engine.py::build_graph()`) is
always computed fresh on every `/graph/*` request — there's nothing to
invalidate. "Rebuild graph" exists to give that action concrete, honest
meaning: it forces a fresh build right now and reports what it found,
rather than pretending to warm a cache that doesn't exist. The one real,
clearable cache in the process is `get_settings()`'s `@lru_cache`
memoization; "Clear cache" clears exactly that, so an updated environment
variable can take effect on the next request without a full restart.

### Known limitations

- Import is validate-and-preview only, by design (see above) — there is
  no "Apply" button and none is planned for this release.
- `default_import_path` is display-only — no import flow reads it yet to
  pre-fill a file path.
- `build_date` is always `null` — there is no build pipeline that stamps
  one; `commit` is best-effort (`git rev-parse --short HEAD` against the
  repo root) and is `null` outside a git checkout or if git isn't
  available.
- "Clear cache" only affects `get_settings()`'s in-memory cache — it does
  not re-read environment variables that were already baked into a
  running process's other state (e.g. an already-open SQLite connection).

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
| `ROLE_OS_IMPORTS_DB_PATH`         | `samples/role_os_sample/00_SYSTEM/role_os_imports.db`           | ChatGPT Conversation Importer database (dashboard-owned; schema created automatically on first use) |
| `ROLE_OS_EXTRACTION_DB_PATH`      | `samples/role_os_sample/00_SYSTEM/role_os_extraction.db`        | Knowledge Extraction database (dashboard-owned; schema created automatically on first use) |
| `ROLE_OS_SESSION_DB_PATH`         | `var/role_os_dashboard/role_os_session.db`                     | Daily Session database (dashboard-owned; schema and the default project registry are created automatically on first use). Deliberately defaults under the git-ignored `var/` directory, not `samples/` -- session data is real personal data, not a checked-in fixture |
| `ROLE_OS_OBSIDIAN_DAILY_NOTES_DIR`| *(empty)*                                                       | Optional path to an Obsidian vault's Daily Notes folder. When set to an existing directory, the Session page's "Save to vault" action writes the generated daily Markdown record there as `YYYY-MM-DD.md`. Never hardcode this -- it's personal and machine-specific |
| `ROLE_OS_ECOSYSTEM_DECISION_LOG_PATH` | *(empty)*                                                   | Optional path to the ROLE Ecosystem's own `role-ecosystem/DECISION_LOG.md`. When set and readable, the Session page's "Recent ecosystem decisions" card reads it live; otherwise it shows a small, documented fallback snapshot |

To point the dashboard at a real ROLE Knowledge OS generated by the builder:

```bash
export ROLE_OS_DB_PATH="/path/to/ROLE_KNOWLEDGE_OS/00_SYSTEM/role_os.db"
```

All five databases are intentionally separate: the knowledge DB is
regenerated wholesale each time `builder.py` runs; the projects DB is
mutated incrementally through the `/pi/*` API; the advisor DB is written
only by the recommendation engine; the imports DB is written only by the
`/import/*` API and CLI; the extraction DB is written only by the
`/extraction/*` API (reading conversation content from the imports DB, but
never writing back into it). None of the five is ever clobbered by
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
      search.py, search_models.py           # Advisor Search domain (Sprint 6) — sibling module, not part of the rule engine
    graph/                        # Knowledge Graph domain (Epic 3)
      models.py                     # Node/Edge/Graph data structures + the 12 node/12 relationship types
      engine.py                      # build_graph(): reads all 3 DBs, merges every builder's output
      queries.py                      # neighbors/shortest_path/impact_analysis/search + named example queries
      api_models.py                    # Pydantic response schemas for /graph/*
      builders/                          # One pure build(...) -> (nodes, edges) function per relationship family
        project_graph.py, dependency_graph.py, capability_graph.py,
        knowledge_graph.py, people_graph.py, application_graph.py,
        vendor_graph.py
    imports/                       # ChatGPT Conversation Importer + Explorer domain (Sprint B1 / B1.5)
      parser.py, db.py, service.py, models.py
    extraction/                    # Knowledge Extraction domain (Sprint 4)
      rules.py, db.py, service.py, models.py
    conversation_graph/            # Knowledge Graph domain (Sprint 5) — separate from graph/ above
      models.py, engine.py, api_models.py
    session/                       # Daily Session domain (ROLE OS Dashboard MVP)
      modes.py                       # Source of truth for PLAN/BUILD/CREATE/LAUNCH/OPERATE/LEARN
      db.py, models.py                # SQLite persistence + Pydantic schemas
      markdown.py                      # Pure-function Claude prompt + Obsidian Markdown record generation
      decisions_adapter.py              # Reads role-ecosystem/DECISION_LOG.md live, or a documented fallback
    routers/
      health.py, projects.py, search.py, knowledge.py   # Milestone 1 API (unchanged)
      ui.py                                                # Dashboard page + /ui/recent, /ui/timeline
      pi/                                                    # Project Intelligence routers, namespaced /pi
        workspaces.py, projects.py, collections.py,
        capabilities.py, dependencies.py, health.py
      advisor.py                                               # Advisor API, namespaced /advisor
      advisor_search.py                                         # Advisor Search API (Sprint 6), namespaced /advisor/search
      graph.py                                                  # Knowledge Graph API, namespaced /graph
      imports.py                                                 # ChatGPT Conversation Importer + Explorer API, namespaced /import
      extraction.py                                               # Knowledge Extraction API, namespaced /extraction
      conversation_graph.py                                        # Knowledge Graph (Sprint 5) API, namespaced /conversation-graph
      settings.py                                                   # Settings API (Sprint 8), namespaced /settings
      session.py                                                     # Daily Session API (ROLE OS Dashboard MVP), namespaced /session
    templates/
      index.html               # Command Center app shell (Jinja2): sidebar + header + #view-root
    static/
      css/
        style.css                 # 4-line @import entry point
        colors.css, layout.css,
        components.css, animations.css   # Design system (Epic 4); colors.css also carries
                                            # the light-theme @media override (ROLE OS Dashboard MVP)
      js/app.js                  # Hash router + every view (Home, Dashboard, Session, Projects,
                                    # Project detail, Knowledge, Advisor, Graph, Assets, Settings)
                                    # + createGraphView()
  tests/                    # API, UI, Health Score, Projects DB, Advisor, and Graph tests (pytest + TestClient)
  requirements.txt
```
