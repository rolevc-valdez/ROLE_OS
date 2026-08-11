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
**Cockpit**, **Knowledge**, **Explorer**, **Advisor**, **Graph**,
**Knowledge Graph**, **Assets**, **Settings**.
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

### Mission Control — the primary Home experience (Sprint C5)

The default route ROLE OS opens to. Answers, within one screen: what should
I work on today, where did I left off, what changed since my last session,
what needs attention, and what's closest to producing real value. One
endpoint, `GET /mission-control` (`app/mission_control/service.py`),
returns the entire already-shaped payload — the frontend
(`renderMissionControlPage` in `static/js/app.js`) performs no ranking,
joining, or deduplication itself.

- **Primary Focus** — one dominant card: the same project Home's ranking
  (`suggested_project_to_continue`) recommends, with its canonical
  `ProjectContext` embedded (health, status, next action, latest snapshot,
  latest AI session, resume state) plus the human-readable reasons behind
  the recommendation. An honest empty state (with the best available
  action) when nothing qualifies.
- **Today's Focus** — up to 3 deduplicated, highest-priority items from
  the Workspace Advisor's rule engine (`workspace.advisor.generate_
  recommendations`) — the same rules Dashboard's Needs Attention uses, not
  a second engine.
- **Since Last Time** — real changes (commits, snapshots, AI sessions,
  adoptions, discovered assets) since the user's last Daily Session
  (`app.session.db`), or a clearly labeled 24h fallback window when no
  session has ever been recorded. Filesystem-mtime-only noise is excluded.
- **Needs Attention** — unresolved issues, most severe first, plus a
  workspace-wide item when the Discovery scan itself is stale.
- **Value Signal ("Closest to Launch")** — surfaces the Workspace
  Advisor's `rule_near_completion` output when a project actually
  qualifies (health score + client-ready/production commercial readiness);
  an honest "insufficient evidence" message otherwise. No revenue/market
  potential is ever fabricated.
- **Portfolio strip** — a compact, one-row-per-adopted-project overview;
  clicking opens the canonical Project Detail/Cockpit, never a second
  Projects page.
- **Recent Activity**, **Daily Session** state (Start/End My Day, reusing
  the existing `/session` domain as-is), **Snapshot Continuity** (prompts
  for a snapshot before switching/ending the day when the recommended
  project has none), and **Quick Actions** (Resume Work, Start New AI
  Session, Create Snapshot, Rescan Workspace, Open Explorer/Assets, Review
  Advisor).

Performance: both this endpoint and `GET /dashboard/summary` used to walk
every adopted project's filesystem for assets 3-4 times per request
(`ProjectContext.assets_count`, Home/Mission Control's recent-assets list,
the activity feed, called twice). `app.assets.service.request_scope()`, a
`contextvars`-backed cache keyed by resolved root path, collapses this to
one walk per adopted project per request when either endpoint's handler
runs inside it.

### Home (superseded by Mission Control, Sprint C5 — kept for reference)

Home's route (`#/home`) now renders Mission Control; the sections below
describe the original "Command Center" page, whose render function
(`renderHome`) is still in `static/js/app.js` but no longer reachable from
the sidebar.

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

### Dashboard page — Dashboard 2.0 (Sprint C2, replacing Sprint 7)

The executive dashboard over the real workspace: adopted projects, health,
recommendations, activity, assets, and sessions — answering "what's
active," "what needs attention," "what changed recently," "what should I
continue," and "how healthy is the portfolio." Sprint 7's Dashboard showed
`GET /import/metrics` (Explorer's own extracted-knowledge-object counts)
under this nav item; those numbers were honestly zero whenever no ChatGPT
conversation had been imported, even though the real workspace already had
adopted projects, commits, and sessions. That rendering path has been
**removed**, not left underneath the new one — `renderDashboardPage` is
now backed entirely by one endpoint, `GET /dashboard/summary`
(`app/dashboard/service.py`), which composes `ProjectContext` and the
existing Home/Advisor/Activity/Assets/Knowledge services rather than
introducing a parallel aggregation engine. Every value on this page is
presentation of an already-shaped field; nothing (health tier, next
action, resume availability, recommendation priority) is recalculated
client-side.

- **Executive summary cards**: Adopted Projects, Healthy, Needs Attention,
  Dirty Repositories, With Next Action, Active AI Sessions, Recent
  Snapshots, Reusable Assets, Knowledge Cards, Recent Commits — all real
  counts over the same `ProjectContext` list every other project-oriented
  screen uses (see the Project Context section below), plus `app.db`'s
  Knowledge count for the one genuinely separate domain.
- **Portfolio Status** — Healthy/Warning/Critical (from `ProjectContext.
  health`), Active/Inactive (`workspace.advisor.last_activity_age_days`/
  `INACTIVE_DAYS_THRESHOLD`, the same threshold `rule_inactive` already
  uses), and Launch-ready (`workspace.advisor.rule_near_completion`,
  called directly — not a new heuristic). Groups, not a strict partition:
  a project can appear in more than one.
- **Continue Work** — one recommendation, reusing `workspace.portfolio.
  suggested_project_to_continue` verbatim (the same ranking Home's Quick
  Resume already uses), with the project's canonical `ProjectContext`
  embedded for its Resume Work button/next action/latest snapshot/reasons.
- **Needs Attention** — `workspace.advisor.generate_recommendations`'s
  full rule set (dirty git tree, no tests, no roadmap, inactive, high move
  risk, near-completion, **plus one rule added this sprint**,
  `rule_snapshot_blocker`, surfacing a blocker recorded in a project's
  latest AI session snapshot — real evidence no prior rule exposed), each
  item linking to its canonical project identity via an embedded
  `project_context`.
- **Recent Activity** — `workspace.service.list_activity_feed`'s existing,
  deduplicated feed (git commits, snapshots, AI sessions, assets, adoption
  events, filesystem changes).
- **Recent Assets** — a compact list from `workspace.service.
  list_project_assets` (no Asset Library redesign).
- **Recent Knowledge** — real `app.db` Knowledge counts and recent cards;
  Knowledge stays a separate domain (a different SQLite file, matched to
  projects only by a soft, free-text name cross-reference), reflected
  honestly rather than pretended to be unified.
- **Empty states** are explicit and honest, never a misleading zero: "No
  reusable assets detected.", "Knowledge has not been imported yet.", "No
  recent activity yet.", "Nothing needs attention right now.", "Not yet
  defined -- no project has an open next action yet."
- A stale-discovery-data banner appears when `workspace.service.
  get_freshness()` reports the last scan is past its staleness threshold.

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

### Assets page — Assets OS (Sprint C4)

A visual Asset Library over real files discovered inside adopted
projects — never a listing derived from the Knowledge Graph. Backed by
the canonical `/assets` API (`app/routers/assets.py`) and the shared
`AssetRecord` model (`app/assets/model.py`), the same model Explorer's
Asset results and Project Hub's Assets summary use — one asset index,
reused everywhere.

- **Gallery (default) and list views**, remembered locally
  (`localStorage`), with real thumbnails for supported raster/SVG images
  (`GET /assets/{id}/preview`) and a type-specific placeholder for
  everything else, including previews that fail (unsupported format, an
  oversized/corrupt source file).
- **Deterministic classification** (`app/assets/classification.py`, no
  LLM): 16 categories from filename/folder-path regex, image dimensions,
  and extension, in a fixed priority order — every category has a reason
  a human can verify by reading the filename/folder themselves.
- **Reusable-by-default rules** with user overrides (reusable, category,
  favorite) stored only in `role_os_assets.db`'s `asset_overrides` table
  — a scanned source file is never modified, copied, moved, renamed,
  edited, or deleted.
- **Duplicate detection** via partial-content hash, grouped but never
  auto-consolidated — the user decides what to do with a duplicate.
- **Server-side filters/search/pagination**; the frontend never computes
  category, reusable status, duplicates, or MIME type client-side.
- **Asset Detail panel**: large preview, full metadata, duplicate-group
  membership, override controls, and Open File / Open Folder / Copy Path
  / Open Project actions — no destructive action anywhere in this
  feature.
- **Security**: every preview/file/open request resolves exclusively
  through `resolve_safe_path`, which re-derives the real filesystem path
  from a validated `asset_id` already present in the live index and
  checks it resolves inside a currently-adopted project root — a client
  can never submit an arbitrary path. See
  [`docs/architecture/17_ASSETS_OS_SPRINT_C4_REPORT.md`](../docs/architecture/17_ASSETS_OS_SPRINT_C4_REPORT.md)
  for the full security model, classification rules, and known
  limitations.

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
| GET/PUT | `/pi/projects/{id}/ai-workspace`                                       | Get / Save Conversation: this project's saved Claude/ChatGPT/Gemini URL, role, preferred model (v1.3) |
| POST   | `/pi/projects/{id}/ai-workspace/open`                                    | `{"tool": "claude"\|"chatgpt"\|"both"}` — the saved URL per tool, or its homepage if none is saved (v1.3) |

### AI Sessions API (v1.4 "Context Engine" — new, nested under `/pi/projects/{id}`)

Entirely additive; introduces no change to any route above, including
the v1.3 AI Workspace routes directly above this section (both APIs
coexist — see `docs/product/DECISIONS.md`). Two new tables in the
existing `role_os_projects.db`; v1.3's saved URLs are copied forward
into this collection once, at upgrade time, by a tracked migration.

| Method | Path                                                     | Description |
|--------|-----------------------------------------------------------|--------------|
| GET    | `/pi/projects/{id}/ai-sessions?assistant=&status=&favorite=` | List this project's AI Sessions (filterable) |
| POST   | `/pi/projects/{id}/ai-sessions`                              | Create a session (`assistant` required: claude/chatgpt/gemini/other) |
| GET    | `/pi/projects/{id}/ai-sessions/{session_id}`                  | Get a session |
| PATCH  | `/pi/projects/{id}/ai-sessions/{session_id}`                   | Update title/URL/role/preferred_model/status/favorite/notes |
| DELETE | `/pi/projects/{id}/ai-sessions/{session_id}`                    | Delete a session (cascades its snapshots) |
| POST   | `/pi/projects/{id}/ai-sessions/{session_id}/set-current`          | Mark current for its (project, assistant) pair |
| POST   | `/pi/projects/{id}/ai-sessions/{session_id}/open`                  | Saved `conversation_url`, or the assistant's homepage |
| POST   | `/pi/projects/{id}/ai-sessions/{session_id}/snapshots`              | Record a Session Snapshot |
| GET    | `/pi/projects/{id}/ai-sessions/{session_id}/snapshots`               | List snapshots, most recent first |
| GET    | `/pi/projects/{id}/ai-sessions/{session_id}/resume`                   | Resumes this specific, explicitly-chosen session -- prompt built from Project Memory (Sprint C7.1), not the session/snapshot alone |
| GET    | `/pi/projects/{id}/memory`                                              | Sprint C7.1: Project Memory -- Cockpit's primary card |
| GET    | `/pi/projects/{id}/timeline`                                            | Project Timeline: all sessions + snapshots for this project, in order |

### Advisor API (Epic 2 — new, namespaced under `/advisor`)

Entirely additive; introduces no change to any route above.

| Method | Path                                                       | Description |
|--------|-------------------------------------------------------------|--------------|
| GET    | `/advisor/recommendations?workspace=&project_id=&recommendation_type=&minimum_priority_score=&include_dismissed=` | List recommendations (filterable) |
| GET    | `/advisor/recommendations/{id}`                                | Get one recommendation |
| GET    | `/advisor/operational-intelligence`                                | Sprint C6: the full canonical Operational Intelligence Engine output (stateless, always fresh) |
| GET    | `/advisor/daily-brief?workspace=`                                | Structured Daily Brief |
| POST   | `/advisor/recommendations/{id}/dismiss`                            | Dismiss a recommendation (persists forever) |
| POST   | `/advisor/recommendations/{id}/complete`                             | Mark a recommendation completed (persists forever) |

`GET /advisor/recommendations` and `GET /advisor/daily-brief` both refresh
the recommendation engine for the requested scope before reading — so the
data is always current without a separate "generate" endpoint, the same
pattern Epic 1 uses for `GET /pi/projects/{id}/health`. `GET /advisor/
operational-intelligence` (Sprint C6) is additive and does not replace or
change either of the above -- see "Operational Intelligence Engine" below.

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

### AI Launcher API (v1.2 — new, namespaced under `/launcher`)

Entirely additive; introduces no change to any route above. Owns no
persistence -- reads the active session (`/session/current`) and recent
ecosystem decisions. Never touches the clipboard or the browser itself;
returns text and URLs only, for `static/js/app.js` to act on client-side.

| Method | Path                | Description |
|--------|----------------------|--------------|
| POST   | `/launcher/start`     | Body `{"tool": "claude" \| "chatgpt" \| "both"}`. Returns the assembled session prompt and the target URL(s). 409 if no session is active; 422 for an unrecognized tool. |

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

### Discovery Engine (Sprints 1-3, `dashboard/app/discovery/`)

Answers "what already exists on disk?" before anything is imported into
Project Intelligence. Strictly read-only against the scanned root: it only
ever calls `os.scandir`/`Path.exists`/local read-only `git` subcommands, and
never follows a symlink or NTFS junction into a cycle. See
`docs/architecture/08_IMPORT_ENGINE_PROPOSAL.md` for the full architecture
and rollout plan, and `09_DISCOVERY_ENGINE_SPRINT1_REPORT.md` /
`10_WORKSPACE_ADOPTION_SPRINT2_REPORT.md` /
`11_PROJECT_BOUNDARY_SPRINT3_REPORT.md` for what shipped in each sprint.

```bash
cd dashboard
python -m app.discovery audit --root "C:\Users\you\Documents" --output "C:\path\to\reports" --max-depth 2 --exclude "Old Stuff"
```

For each candidate folder it reports: classification (`Software Project`,
`Website`, `Mixed Project`, `Documentation Project`, `Brand / Asset
Project`, `Unknown`, or `Non-project`) with a confidence score; git
metadata (branch, remote, last commit, dirty state); README/ROADMAP/
CHANGELOG/TODO/LICENSE presence; languages, tech markers, tests, Docker/CI;
image/video/document/design-file/font counts; a **move-safety** rating
(`low`/`medium`/`high`) explaining exactly which hardcoded absolute paths,
`.env` files, launcher scripts, Obsidian vaults, or VS Code workspace files
would break on relocation; a **Health Score** (0-100, weighted across
documentation/tests/recent activity/roadmap/architecture/automation/
commercial-readiness/deployment, each signal individually inspectable in
`health.py`); one of six **recommendations** (`Leave where it is`,
`Move into IA PROJECTS`, `Archive`, `Merge with another project`, `Rename`,
`Requires manual review`); and, since Sprint 3, a **project-boundary /
hierarchy** classification (`app/discovery/boundary/`) -- see below.
`--output` writes `discovery_audit.json` and `discovery_audit.md` (refused
if it resolves inside `--root`), now including Top-level/Nested/Internal/
Excluded/Needs-review sections and a false-positive-reduction comparison.

#### Project Boundary / Hierarchy (Sprint 3, `app/discovery/boundary/`)

Distinguishes a real top-level project from a nested repository/component,
an internal structure folder, an excluded folder, and a non-project --
deliberately a **separate field** (`item_kind`) from `classification`
(which answers "what kind of thing is this", not "where does it sit in the
real project tree"). Every `DiscoveredProject` gains: `item_id` (stable
`sha1(root_path)[:16]`), `item_kind`, `parent_item_id`, `project_root_id`,
`hierarchy_depth`, `is_top_level_project`/`is_nested_repository`/
`is_internal_folder`/`is_excluded`, `exclusion_reason`,
`boundary_confidence`, and `boundary_evidence` (the specific reasons, same
explainability principle as Health Score/Recommendation).

- A folder is a **top-level project** if it has its own `.git`/tech-stack
  marker, **or** contains a nested folder that does (a "factory"/monorepo
  container, e.g. `ROLE Commerce Factory` holding two adapter components),
  **or** has a README plus substantial internal structure (3+ internal
  folders, or a roadmap/changelog).
- A nested folder with its own `.git` is a **repository**; with just a
  package manifest, a **component** -- unless it *also* has strong
  independent-product evidence of its own (own remote, roadmap/changelog,
  high confidence), in which case it's promoted to its own top-level
  project instead.
- A nested folder matching a known internal-structure name (numbered
  `01_*` prefixes, `docs`, `assets`, `src`, `tests`, ... --
  `boundary/rules.py`) becomes **internal_folder**/**documentation**/
  **asset_library** -- unless it has its own markers, which always wins.
- **Exclusions** (`boundary/exclusions_config.json`, the one source-of-truth
  config file): exact names, case-insensitive names, glob patterns, and
  relative-path patterns. Defaults include common technical folders and
  `OTROS - no proyectos`. An excluded folder is reported (with its reason)
  but never walked recursively. Extra exclusions: `ROLE_OS_DISCOVERY_EXTRA_EXCLUSIONS`
  (comma-separated names/globs; never an absolute path) or CLI `--exclude`.

### Workspace Adoption (Sprints 2-3, `dashboard/app/workspace/`, `/workspace/*` API)

The first writable layer over the read-only Discovery Engine. Own SQLite
file (`role_os_workspace.db`): a cache of the last scan, and a small
per-folder overlay (`priority`/`business_value`/`status`/`tags`/`notes`/
`ignored`/boundary `override_action`) -- **never** discovery metadata
(name/git/health/classification/hierarchy), which is always re-read live
from the cached scan. `ROLE_OS_DISCOVERY_ROOT` configures the default scan
root (defaults to this checkout's own parent directory).

- `GET /workspace/summary` — Last Scan / Projects Found / Adopted / Ignored.
- `GET /workspace/discovered[?view=top_level|repositories|excluded|needs_review|all][&include_ignored=]` —
  omitting `view` returns the original Sprint 2 flat list (unchanged
  contract); `view=top_level` (what the Workspace page uses by default)
  groups nested repositories/components/internal folders underneath their
  parent, each with rolled-up counts.
- `GET /workspace/discovered/{id}` — full detail (Review).
- `POST /workspace/rescan` — runs a real scan, preserving every adopted/
  ignored/override state by id; a renamed folder gets a new id (its old
  overlay is orphaned, harmlessly); a removed folder simply disappears.
- `POST /workspace/discovered/{id}/adopt|ignore|unignore`,
  `PATCH /workspace/discovered/{id}`, `POST .../notes`.
- `POST /workspace/discovered/{id}/override` (`{"action": "top_level"}` or
  `{"action": "attach_to_parent", "parent_id": "..."}`) / `.../override/clear`
  — a user correction to the Discovery Engine's computed grouping, stored
  only in the overlay; the computed `item_kind`/`parent_item_id` are never
  altered, so "detected boundary" vs. "your override" stay comparable.
- `GET /workspace/adopted` — adopted items reshaped like `/pi/projects`, so
  the Projects page can show manually-created and discovered projects
  side by side (labeled "Discovered") without special-casing either.
- `POST /workspace/discovered/{item_id}/resume-work` (Sprint 5) — the
  primary Resume Work action; 404 until the item is adopted. See "Project
  Unification (Sprint 5)" below.

The Workspace sidebar page has four filter tabs (Top-level projects /
Nested repositories / Ignored & excluded / Needs review), an Expand action
per top-level project to reveal its children indented underneath, and a
Review detail panel showing the full boundary evidence plus override
actions.

#### Project Intelligence Wiring (Sprint 4)

Wires the Sprint 1-3 data into Projects, Home, Advisor, and Assets, which
previously showed empty/zero-centric content whenever no manually-created
Project Intelligence data existed. Scoped to **adopted top-level projects
only** (`list_enriched_top_level_projects(adopted_only=True)`) -- adoption
is the existing, explicit "track this" signal, so excluded/internal-folder
items can never leak into any of these views.

- **Next Action** (`app/discovery/next_action.py`): a deterministic,
  non-LLM search, in priority order -- AI Session Snapshot hint (passed in
  by the caller; this module has no DB access) → `NEXT_ACTION.md` →
  `TODO.md`/a `## TODO` section → `ROADMAP.md`'s current milestone →
  README's "Next Steps" → `CHANGELOG.md`'s unreleased section → the
  latest git commit message. Every result carries its source, source
  path, confidence, and extraction timestamp; nothing found means
  `text: None` ("Not yet defined"), never an invented value.
- **Assets** (`app/workspace/assets_index.py`): real discovered asset
  records (PNG/JPG/JPEG/WEBP/SVG/PDF/MP4/MOV/PSD/AI/fonts) per adopted
  project -- filename/path/type/size/modified/category/reusable/a
  partial-hash (first 1MB) duplicate signal. No thumbnails, no copying.
- **Workspace Advisor 2.0** (`app/workspace/advisor.py`): 11 evidence-only
  rules (inactive-N-days, dirty git tree, no README/roadmap/tests,
  next-action-available, high-value-but-inactive, high move risk,
  momentum, assets-without-commercial-output, near-completion) -- a
  sibling to `app/advisor/` (Epic 2, which has no filesystem/git
  knowledge), not a rewrite. Every recommendation carries project/reason/
  evidence/priority/confidence/action_link; nothing fires without real
  supporting data.
- **Recent Activity** (`app/workspace/activity.py`): merges git commits
  (`git log -5` per repo), filesystem mtimes, adoption events, AI
  Sessions/Snapshots, and discovered assets into one deduplicated,
  time-sorted feed.
- **Home portfolio** (`app/workspace/portfolio.py`): Last Active Project,
  Most Recently Modified, Projects Needing Attention, Recent Commits,
  Recent Assets, Latest AI Session, a Suggested Project to Continue
  (explainable: has a next action + recent activity + business value),
  and a Quick Resume action.
- API (additive): `GET /workspace/home`, `GET /workspace/advisor`,
  `GET /workspace/assets[?project_id=]`, `GET /workspace/activity[?limit=]`;
  `GET /workspace/discovered?view=top_level` is now enriched with
  `next_action`/`documentation_status`/`test_status`/`asset_count`;
  `GET /workspace/discovered/{id}` now includes `next_action`/
  `ai_sessions`; `GET /workspace/summary` gained `is_stale`/
  `hours_since_scan`/`stale_threshold_hours` (stale after 24h).
- UI: Projects page cards show the full field set (git/docs/tests/assets/
  next action/adoption status), linking to a new Discovered Project Detail
  view (`#/dproject/{id}`, parallel to and never touching the existing
  manual-project detail view) with Overview/Git/Documentation/
  Repositories-Components/Assets/Tests/Recent Activity/AI Sessions/Latest
  Snapshot/Next Action/Risks-Blockers sections. Home gained a "Your
  Projects" section above the untouched Today's Focus. Advisor gained a
  "Discovered Projects" section. Assets was rebuilt from an inert
  placeholder into a real table.
- **Known gap**: AI Sessions/Snapshots cannot yet be *created* for a
  purely-discovered project -- `app.projects.db.create_ai_session`
  requires a real row in the `projects` table (enforced by both an
  explicit check and a SQLite foreign key), which a discovered-only item
  never has. The read side is fully wired (a discovered item's `ai_
  sessions` correctly returns empty/`None` today, never an error), so
  this surfaces honestly as "Not yet defined" rather than breaking --
  but starting a new AI session *from* a discovered project's detail page
  isn't possible until a future sprint decides how the two id schemes
  should relate.

#### Project Unification (Sprint 5)

Closes Sprint 4's "known gap" above by removing the conceptual split
between manually-created Projects and discovered/adopted projects
entirely -- from the user's side there is now exactly one concept,
"Project," bridged rather than merged.

- **Canonical Project Identity** (`app/workspace/identity.py`): a
  bidirectional nullable bridge -- `projects.discovery_item_id` (Project →
  discovery item) and `adopted_projects.canonical_project_id` (discovery
  item → Project) -- resolved lazily and idempotently by
  `get_or_create_canonical_project_id()`: reuse an existing valid link →
  link an unlinked manual Project with a matching name (case-insensitive;
  never overwrites existing Project fields) → create a minimal new
  Project (name + `Discovered` workspace only, never a copy of discovery
  metadata). A stale link (its Project row deleted out-of-band) silently
  re-resolves rather than returning a dangling id. `adopt_item` now
  resolves a canonical identity as part of adoption itself, and
  `enrich_project_item` self-heals one for any already-adopted item that
  doesn't have one yet -- so AI Sessions now work for every adopted
  project with zero manual setup, closing Sprint 4's gap.
- **Resume Work** (`app/workspace/resume.py`, `POST /workspace/discovered/
  {item_id}/resume-work`): the one primary action on a project. **Redesigned
  in Sprint C7.1** -- resumes the *Project* via Project Memory
  (`app/project_memory/`), not the AI Session; see "Resume Work Refactor"
  below for the full design. Selects (or creates) the best AI Session,
  marks it current, builds the Resume Prompt from Project Memory, resolves
  the assistant conversation URL (or a homepage fallback), and touches
  `last_used_at`. 404s until the item is adopted. Wired as the primary
  action on the Discovered Project Detail view, Home's Quick Resume card,
  Mission Control's Primary Focus card, and every Workspace Advisor
  recommendation -- all trigger real session creation, not just
  navigation.
- **History wiring fix**: `get_enriched_item` previously queried AI
  Sessions using the raw discovery-item hash, which never matched a real
  `projects.id` and silently returned empty results (Sprint 4's
  documented gap). It now resolves the canonical id first, and also
  surfaces a `timeline` field (`projects_db.list_project_timeline`) on
  the Discovered Project Detail view.
- **Backward compatibility**: existing manually-created projects are
  unaffected; the projects list dedupes so a project linked to a
  discovered item never appears twice.
- **Known limitation**: the identity match for backward-compat migration
  is exact-name (case-insensitive) only -- a manual Project named
  differently from its matching folder will not auto-link and instead
  gets its own new canonical Project on first adoption. See
  `docs/architecture/13_PROJECT_UNIFICATION_SPRINT5_REPORT.md` for the
  full write-up.

#### Project Context (Sprint C1: Consolidation)

`app/project_context/` -- a single, reusable service that assembles
everything a UI screen needs to describe one project (identity, health,
git, commits, next action, a normalized advisor summary, assets/
documents/knowledge counts, timeline, resume state), reusing Discovery/
Workspace/Project Intelligence/Advisor exactly as they already work. Not
a new "project" concept -- a composition layer over the existing ones.

- `build_project_context(item_id=..., project_id=...)`: resolves either
  identity (or both) to the same object. `build_project_contexts_for_
  workspace()`: the bulk variant for list pages, reusing the existing
  enrichment pass at no extra per-item cost (it skips the Epic 2 advisor
  call and full timeline -- cost knobs, not shape differences).
- API: `GET /project-context` (bulk, adopted-only by default),
  `GET /project-context/{identifier}` (item id or canonical/PI project
  id; 404 if neither resolves).
- Two real bugs fixed while centralizing this (not rewrites -- the same
  functions, called correctly instead of inconsistently):
  `get_home_portfolio`'s `latest_ai_session` was silently always `None`
  (nothing had ever attached the AI session summary `enrich_project_item`
  already computed); `get_enriched_item` looked up the same AI session
  summary twice per call.
- `GET /workspace/activity` and `GET /workspace/assets` both gained an
  optional `project_id` filter, applied server-side (restricting the
  underlying git/filesystem work), replacing the Discovered Project
  Detail page's previous approach of fetching every adopted project's
  activity and filtering it client-side.
- Cockpit's "Next Action" card now consults `/project-context/{id}`
  first (falling back to its prior snapshot-only computation on any
  fetch failure), so a project linked to a discovered folder shows the
  same richer, multi-source next action Workspace's own detail view
  already had.
- **Sprint C1B (Rewiring)**: a consolidation audit found the above wiring
  was the module's *only* production caller -- every other screen
  (Home, Projects, Workspace, Advisor) still independently assembled its
  own project data, and the module's own health-tier thresholds (80/50)
  disagreed with the frontend's (70/40). C1B made `ProjectContext` load-
  bearing: `GET /workspace/discovered?view=top_level`, `GET /workspace/
  home`, `GET /workspace/discovered/{id}`, `GET /pi/projects`,
  `GET /pi/projects/{id}`, `GET /workspace/advisor`, and
  `GET /advisor/recommendations` now all embed a real `project_context`
  per project/recommendation; Cockpit reads it off the `/pi/projects` row
  it already fetched instead of a separate call. Health-tier thresholds
  now live in one place (`app/project_context/health.py`); the inline
  next-action mini-extractor and the disconnected `resume_state` stub were
  removed in favor of the same canonical extractor
  (`discovery.next_action.extract_next_action`) and a new read-only
  `workspace.resume.preview_resume_state()`; `assets_count` now matches
  the real Assets index exactly. See the Sprint C1B completion report
  (delivered as a published artifact) for the full before/after.

### Dashboard 2.0 (Sprint C2)

`app/dashboard/service.py` -- one additive endpoint, `GET /dashboard/
summary`, composing `ProjectContext` (workspace + manual PI projects),
`workspace.service.get_home_portfolio`, `workspace.advisor.
generate_recommendations`, `workspace.service.list_activity_feed`/
`list_project_assets`, and `app.db`'s Knowledge counts into one already-
shaped executive-dashboard payload. Replaces the legacy Sprint 7 Dashboard
(`/import/metrics`-backed, zero-centric) -- see "Dashboard page" above for
the full breakdown of what the page shows. Not a new aggregation engine:
every field is produced by calling an existing service exactly once and
counting/grouping its output. The one new rule, `rule_snapshot_blocker`
(a project's latest AI-session-snapshot blocker), was added to the
existing `workspace/advisor.py` rule set because no existing service
surfaced that evidence -- not a new engine, the same pure-function-per-
enriched-item shape as the other eleven rules.

### Explorer 2.0 (Sprint C3)

`app/routers/explorer.py` / `app/explorer/service.py` -- `GET /explorer/
search?q=` is a universal `ProjectContext` search across 13 result types
(project, discovered folder, AI session, decision, document, asset,
person, application, task, idea, deliverable, note, activity), each with
its own `actions` (e.g. an Asset result's primary action opens the real
Asset Detail panel). Replaces the legacy Conversation Explorer browsing
UI (Imported Conversations list, conversation database counters, import
statistics) entirely -- Explorer no longer has any dependency on the
imports domain. `GET /explorer/project-hub/{id}` composes the same
`ProjectContext` plus a per-project assets summary into one hub view. No
duplicated aggregation: both reuse `app.project_context.builder.
all_project_contexts()` and `app.assets.service.list_all_assets()`, the
same functions every other screen calls.

### Assets OS (Sprint C4)

`app/assets/` / `app/routers/assets.py` -- replaces the Assets page's
flat technical file listing (`Asset` nodes from the Knowledge Graph) with
a real visual Asset Library over files discovered inside adopted
projects. See "Assets page" above for the full feature breakdown and
[`docs/architecture/17_ASSETS_OS_SPRINT_C4_REPORT.md`](../docs/architecture/17_ASSETS_OS_SPRINT_C4_REPORT.md)
for the canonical `AssetRecord` model, preview security model, cache
location, classification rules, and known limitations. `app.workspace.
assets_index` (Sprint 4) is now a thin backward-compatible shim
delegating to `app.assets.service` -- one asset index, not two.

| Method | Path                                          | Description |
|--------|------------------------------------------------|--------------|
| GET    | `/assets?q=&category=&project_id=&reusable=&favorite=&duplicates_only=&page=&page_size=` | List/search/filter/paginate assets |
| GET    | `/assets/freshness`                           | Last scan time / staleness |
| GET    | `/assets/duplicates/{group_id}`               | Every member of a duplicate group |
| GET    | `/assets/{id}`                                | Full asset detail |
| GET    | `/assets/{id}/preview`                        | Cached, resized preview image (or 422 if unsupported/unsafe) |
| GET    | `/assets/{id}/file`                           | Raw file stream |
| PATCH  | `/assets/{id}`                                | Set reusable/category/favorite override |
| POST   | `/assets/{id}/open-file`, `/assets/{id}/open-folder` | OS-integration actions (this machine only, Windows) |

#### Assets Canonicalization Audit (Sprint C4.1)

An audit sprint verifying `app.assets` is the *only* place asset
classification/duplicate-detection/counting logic lives across Assets,
Explorer, Project Hub, Home, Dashboard, and ProjectContext -- confirmed
via a full symbol-level caller audit, with 9 new architectural guard
tests (`test_assets_canonical_architecture.py`) that inspect the source
tree itself so a second implementation can't quietly reappear. Found and
fixed one real cross-screen bug: `index_project_assets` (called directly
by Dashboard/Home/`ProjectContext.assets_count`/Project Hub, not just the
`/assets` API) never resolved `duplicate_group_id` to `None` for a
genuinely unique file. See
[`docs/architecture/18_ASSETS_CANONICALIZATION_SPRINT_C41_REPORT.md`](../docs/architecture/18_ASSETS_CANONICALIZATION_SPRINT_C41_REPORT.md)
for the full audit findings, including the deliberate distinction between
`app.assets.AssetRecord` (real files) and the Knowledge Graph's `"Asset"`
node type (an unrelated, pre-existing knowledge-extraction concept with
no id/endpoint overlap).

### Mission Control (Sprint C5)

`app/mission_control/service.py` / `app/routers/mission_control.py` -- one
additive endpoint, `GET /mission-control`, composing `ProjectContext`,
Home's ranking (`get_home_portfolio`/`suggested_project_to_continue`),
`workspace.advisor.generate_recommendations`, `workspace.service.
list_activity_feed`, and `app.session.db` into the daily operating
surface's already-shaped payload -- see "Mission Control" above for the
full section-by-section breakdown. No new ranking/recommendation engine:
every field is produced by calling an existing service exactly once.
Fixes the Sprint C4.1 finding (`GET /dashboard/summary` walking every
adopted project's assets twice) with `app.assets.service.request_scope()`,
a request-scoped filesystem-walk cache both this endpoint and Dashboard's
now use -- see `docs/product/DECISIONS.md` for the full reasoning and known
limitations (Since Last Time cannot yet surface status/blocker/roadmap
changes as discrete events, only what the existing Recent Activity feed
tracks).

| Method | Path               | Description |
|--------|--------------------|--------------|
| GET    | `/mission-control` | The entire Mission Control payload (primary focus, today's focus, since last time, needs attention, value signal, portfolio, recent activity, daily session, snapshot continuity, quick actions) |

### Operational Intelligence Engine (Sprint C6)

`app/operational_intelligence/` -- one canonical service,
`get_operational_intelligence()`, that turns evidence about a project (or
the workspace as a whole) into a recommendation. No LLM, no embeddings, no
vector database, no external AI API -- every recommendation traces back to
a deterministic rule over already-computed evidence. Every recommendation
carries exactly seven fields: `recommendation`, `priority` (0-100),
`confidence` (0.0-1.0), `evidence` (list of concrete facts), `project`
(a reference, or `None` for a workspace-wide item), `expected_benefit`
(a static, documented keyword-lookup sentence -- never generated), and
`suggested_action` -- plus `reason`/`action_link`/`source`/`rule_id` extras.

Not a new engine so much as one composition over the two that already
existed:

- **Discovery pack** -- `workspace.advisor.generate_recommendations`
  (git status, health, README/roadmap/tests presence, next action,
  business value, move risk, momentum, commercial readiness, snapshot
  blockers), reused verbatim.
- **PI pack** -- `app.advisor.engine.get_recommendations` (dependencies,
  capabilities, TODOs, deliverables, decisions, staleness, near-
  completion), called once for the whole workspace and reused verbatim --
  its persisted dismiss/complete/TTL lifecycle (Advisor-specific state)
  is untouched.
- **New evidence pack** (`app/operational_intelligence/rules.py`) --
  three previously-uncovered evidence dimensions: Knowledge freshness (new
  -- how long since the last ChatGPT conversation import,
  `KNOWLEDGE_STALE_DAYS = 30`), Discovery scan freshness (already computed
  by `workspace.service.get_freshness`, now turned into an actionable
  recommendation), and workspace status crossed with pending work (a
  paused/archived project that still has open next-action/pending-snapshot
  work).

**Conflict resolution**: recommendations are deduplicated by `(project,
recommendation title)` -- an identical title firing for the same project
(or workspace-wide) from two different rule packs collapses to whichever
has the higher priority, then confidence. **Priority**: no new scoring
formula -- every rule pack already returns a 0-100 integer; the engine only
sorts by it.

**Consumers**: Mission Control's Today's Focus/Needs Attention/Value
Signal/Daily-Session-suggestion-text; the additive `GET /advisor/
operational-intelligence` endpoint; Explorer's Recommendation search
results (now carrying an `evidence` field). See `docs/product/DECISIONS.md`
for the full reasoning, including why Resume Work and Dashboard were
deliberately left as lighter-touch integration points this sprint.

| Method | Path                             | Description |
|--------|-----------------------------------|--------------|
| GET    | `/advisor/operational-intelligence` | The full canonical recommendation list (all three rule packs, normalized, deduped, sorted) |

### Resume Work Refactor (Sprint C7.1)

`app/project_memory/` -- fixes a real product flaw real-world validation
surfaced: Resume Work resumed an *AI Session*, not a Project. A thin or
generic session/snapshot meant a thin, generic prompt, and the assistant
had to ask what the project even was. Corrected flow:

```
Project -> Project Memory -> Resume Prompt -> locate best AI Session
-> open conversation -> copy prompt
```

The AI Session is now only ever the transport (where the conversation
happens to live); Project Memory is the one source of truth for the
prompt.

- **Project Memory** (`service.py`) composes the same already-computed
  `ProjectContext` (next action, git, latest snapshot) plus, for a real
  Resume Work click, the Operational Intelligence Engine's top
  recommendation for that project -- never recomputed independently.
- **Resume Prompt** (`prompt.py`) always begins with exactly `Project:`,
  `Current Objective:`, `Where We Left Off:`, `Pending Work:`,
  `Next Action:`, `Operational Recommendation:`, `Conversation:`, in that
  order. Session data (title, assistant) appears *only* in the
  `Conversation:` section, alongside why that session was picked -- never
  as a source for any other section.
- **Conversation selection** (`session_selection.py`): prefers 1) the
  latest active session, 2) a pinned session (`favorite` -- the only
  "pin"-like field that exists on `AISession`; no second concept was
  invented), 3) a preferred session (`current` -- the closest existing
  concept to a per-project "preferred" session), 4) the newest session.
  Every choice returns a plain-English reason, never a silent decision.
- **Session naming** (`naming.py`): every session Resume Work creates (or
  retitles, if it inherited a generic name from the old flow) is named
  `<Project Name> — <Objective>` (e.g. "ROLE Commerce Factory — Shopify
  Adapter") -- never "Resume Work", "Untitled", or "Session 1". A session
  already titled "Resume Work" (the exact bug this sprint fixes) is
  retitled the moment it's next resumed.
- **Cockpit**: Project Memory (`GET /pi/projects/{id}/memory`) replaces
  the old Today's Objective/Next Action/Last Snapshot insight cards as the
  primary card; AI Sessions is now a secondary section below it.
- **Mission Control**: no frontend changes needed -- Resume Work's
  existing endpoint (`POST /workspace/discovered/{id}/resume-work`) now
  builds its prompt from Project Memory automatically.
- **A real recursion, fixed with two cost knobs, not a parallel builder**:
  `ProjectContext`'s `resume_state` builds Project Memory (for an accurate
  preview prompt), which itself calls `build_project_context` for the same
  project. Two new parameters on `build_project_context`/`_assemble`
  (`include_resume_state`, `include_epic2_recs`), both defaulting to
  `True`, let `app.project_memory` opt out of both (avoiding the
  recursion, and avoiding a redundant Epic 2 Advisor refresh Project
  Memory never needs) without changing behavior for any other caller.
- **Performance**: the real Resume Work click intentionally pays for one
  whole-workspace Operational Intelligence pass (needed for `Operational
  Recommendation:`); every more-frequent caller (`preview_resume_state`,
  Cockpit's memory card, the per-session `/resume` endpoint) skips it and
  stays cheap -- a real regression caught by this sprint's own full
  regression run before it shipped (see `docs/product/DECISIONS.md`).
- **Removed, not deprecated**: the old session-only
  `app.services.resume.build_resume_prompt` and its test file --
  "the AI Session never owns the prompt" is an invariant now, not a
  preference.

### Project Ecosystem Engine (Sprint C8)

`app/project_ecosystem/` -- understands how adopted projects relate to
each other (dependencies, shared assets/knowledge/documentation/prompts/
sessions, blocking relationships) from deterministic evidence only. No
LLM, no embeddings, no vector database.

**Canonical relationship model** (`models.py`): every relationship
carries `relationship_id, source_project, target_project,
relationship_type, confidence, evidence, detector, discovered_at,
last_verified, manual_override, status`. `relationship_type` is always
exactly one of `SUPPORTED_TYPES`: `depends_on, uses, consumes, produces,
extends, shares_assets, shares_prompts, shares_documentation,
shares_knowledge, shares_sessions, blocks, blocked_by, related`.

**Detectors** (`detectors.py`), each reusing an existing canonical domain
rather than re-deriving it:

- **`detect_dependencies` / `detect_capabilities`** -- PI's existing
  explicit dependency/capability tables (`app.projects.db`), reused
  verbatim (confidence 1.0). `blocks`/`blocked_by` are derived from a
  dependency whose target project's own status/health looks blocked --
  not a separate detector.
- **`detect_shared_assets`** -- the canonical Assets index
  (`app.assets.service.list_all_assets`); two projects sharing a
  `duplicate_group_id` share an asset.
- **`detect_shared_knowledge`** -- Knowledge cards (`app.db.
  list_all_cards`), soft-matched to a project via the same case-
  insensitive `card['project']` name convention `ProjectContext`/Explorer
  already use.
- **`detect_shared_documentation` / `detect_git_remote_references`** --
  bounded (20KB, same cap as `discovery.next_action`) reads of each
  project's own README/ROADMAP/CHANGELOG/TODO/NEXT_ACTION and git remote
  URL, searched for another project's name as a literal text reference.
- **`detect_shared_prompts_and_sessions`** -- a project's latest Session
  Snapshot/AI Session mentioning another project by name.
- **`detect_sibling_projects`** -- two adopted projects under the same
  parent folder (`related`, low confidence).

**Conflict resolution & manual overrides** (`relationships.py`, `db.py`):
same-pair-same-type relationships from different detectors merge (union
of evidence, higher confidence kept). A small overlay table
(`role_os_ecosystem.db`) stores only manual dismiss/confirm overrides,
keyed by the relationship's own deterministic id -- the relationships
themselves are never persisted, always recomputed fresh.

**Impact Summary** (`graph.py`): `affected_projects, shared_assets,
shared_documents, shared_prompts, shared_knowledge, shared_sessions, risk,
confidence` -- bounded to direct (1-hop) relationships only, no multi-hop
graph traversal, no destructive action ever taken.

**Consumers**:

- **Project Detail** -- Explorer's Project Hub (`GET /explorer/
  project/{id}`) gained an Ecosystem section: Dependencies, Consumers,
  Blocked By, Blocks, Shared Assets, Shared Prompts, Shared Knowledge,
  Shared Documentation, Impact Summary -- clean cards, never a graph
  visualization, each linking to the related project.
- **Explorer search** -- a new result type, `"Ecosystem Relationship"`
  (`_search_ecosystem`): searching a project name surfaces "Used by ..."
  results (its dependents); searching a relationship keyword (e.g. "shared
  assets", "depends on") surfaces every relationship of that type.
- **Mission Control** -- the Operational Intelligence Engine gained
  `rule_unblocks_dependents` ("Complete X to unblock Y, Z"), reading only
  the cheap dependency detector (plain SQL) rather than the full ecosystem
  (which also runs filesystem/knowledge scans), preserving OI's own
  no-repeated-scans contract.
- **Project Memory** -- a small, bounded `related_projects` section (top
  dependencies/consumers/recent shared decisions -- never a graph dump).

**Real bug found and fixed** while building `detect_shared_assets`:
`app.assets.service.group_duplicates` only ever *cleared* a record's
`duplicate_group_id`, never (re)set it -- since `list_all_assets` calls it
a second time on records that already passed through it once (inside each
project's own `index_project_assets` call), a file whose only duplicate
lived in a *different* project could never be resolved back to a shared
group id, contradicting `list_all_assets`'s own docstring promise. Fixed
at the root; covered by a new regression test in `test_assets_os.py`.

**Performance**: every whole-workspace pass (`compute_relationships`,
Explorer's `search()`/`project_hub()`, Resume Work, Cockpit's memory card)
runs inside `app.assets.service.request_scope()` so the shared-assets
detector's filesystem walk is never repeated within one request.

| Method | Path                          | Description |
|--------|--------------------------------|--------------|
| GET    | `/project-ecosystem/{project_id}` | A project's full ecosystem view (relationships, dependencies, consumers, blocks, blocked_by, shared_assets/prompts/documents/knowledge/sessions, impact_summary) |

**Known limitations**: no import/package-reference (source-code parsing)
detection -- too language-specific and too expensive to do safely at this
sprint's scope; only filesystem/git/documentation/knowledge/PI-data
evidence is detected. Shared-prompts/shared-sessions detection is a
simple name-mention scan (low confidence), not a semantic match. See
`docs/product/DECISIONS.md` for the full reasoning.

### Impact Analysis Engine (Sprint C9)

`app/impact_analysis/` -- answers "if this project changes, what else is
affected?" entirely by reading the Project Ecosystem Engine's (Sprint C8)
already-computed relationship graph, `ProjectContext`, Assets, Knowledge,
Operational Intelligence (Sprint C6), and Project Memory (Sprint C7.1). No
new relationship-detection pass, no new graph, no LLM/embeddings/vector
database. Note: this is unrelated to the pre-existing Knowledge Graph
endpoint `GET /graph/impact/{id}` (Epic 3's node-level cascading
traversal over the Knowledge Graph) -- a separate, older concept with no
overlap in code or data source.

**Canonical `ImpactReport`** (`models.py`): `project, generated_at,
overall_risk, confidence, affected_projects, direct_dependencies,
transitive_dependencies, shared_assets, shared_prompts,
shared_documentation, shared_knowledge, shared_sessions,
operational_effects, release_effects, recommended_actions, evidence,
limitations`. `direct_dependencies`/`transitive_dependencies` name the
projects *affected by* a change to this project (who depends on it, not
what it depends on).

**Risk scoring** (`scoring.py`): five explainable levels -- `none, low,
medium, high, critical` -- each reached by a fixed, documented count
threshold (already-blocking dependents, direct/transitive dependent
counts, total shared-evidence count), never a weighted formula. Every
level returns the exact reason string(s) that produced it.

**Bounded transitive traversal** (`service.py`): a cycle-safe BFS over the
Ecosystem Engine's `depends_on` edges (reversed: who depends on this
project, then who depends on those, ...), bounded to 3 hops -- covers the
brief's own worked example (ROLE OS -> ROLE Commerce Factory ->
RoleValdez.com) with headroom. A visited set keyed by project identity
guarantees no cycle is ever re-entered and no project listed twice.

**Consumers**:

- **Project Detail** -- Explorer's Project Hub (`GET /explorer/
  project/{id}`) gained an Impact Analysis section: Overall Risk, Affected
  Projects, Top Reasons, Recommended Actions -- concise cards, never a
  diagram.
- **Mission Control** -- the Operational Intelligence Engine gained
  `rule_high_impact_change` ("Changing X today will affect N project(s) --
  schedule accordingly"), reading only the cheap dependency-only
  relationships already in `bundle["ecosystem_dependencies"]` and doing
  its own bounded traversal -- never calling the full Impact Analysis
  Engine, preserving OI's own no-repeated-scans contract.
- **Project Memory** -- a compact "Potential Impact" line (risk, affected
  count, up to 3 affected names).
- **Explorer search** -- a new result type, `"Impact"` (`_search_impact`):
  searching a project name surfaces "Impact of changing X: <risk> risk".

**Two real bugs found and fixed** while building this engine: (1)
`project_ecosystem/models.py`'s `BLOCKING_STATUSES` incorrectly included
`"critical"`, and `detectors.py`'s `detect_dependencies` also matched a
target's computed *health tier* of `"critical"` -- conflating an explicit
`blocked`/`at_risk` status with a fresh project's default `health_score=0`
tier, falsely flagging nearly every brand-new project as blocking its
dependents. Fixed at the root in `project_ecosystem`, re-verified against
the brief's own worked example; `test_project_ecosystem.py`'s 23 tests
unaffected. (2) `build_project_memory()` was calling
`get_operational_intelligence()` (a whole-workspace Epic 2 Advisor
refresh) twice per invocation once Impact Analysis's
`operational_effects` needed its own copy -- fixed by computing it once
per call and threading the same result through both the Operational
Recommendation field and Impact Analysis.

**Performance**: reuses the Project Ecosystem graph and
`request_scope()`-cached asset/knowledge data; every consumer that
already computed `all_contexts`/`relationships`/
`operational_intelligence_recs` in the same request passes them straight
through -- no repeated filesystem scan, no repeated relationship
detection, no repeated Operational Intelligence pass.

| Method | Path                          | Description |
|--------|--------------------------------|--------------|
| GET    | `/impact-analysis/{project_id}` | A project's full Impact Analysis report (overall risk, affected projects, direct/transitive dependencies, shared assets/prompts/documentation/knowledge/sessions, operational/release effects, recommended actions, evidence, limitations) |

**Known limitations**: transitive traversal follows only explicit
`depends_on` relationships (Sprint C8) -- an undeclared dependency with no
PI edge is not traversed. Shared-evidence detection inherits the Project
Ecosystem Engine's own limitations (no import/package-reference parsing;
name-mention detectors are literal substring matches). Operational/
release effects are read from each affected project's existing
Operational Intelligence recommendation and business_value/health, never
independently assessed. See `docs/product/DECISIONS.md` for the full
reasoning.

### Executive Decision Engine (Sprint C10)

`app/executive_decision/` -- ROLE OS's move from an information
dashboard to a deterministic decision system. One call answers "what
should I work on next?" using evidence from every existing domain
(Project Context, Operational Intelligence, Project Ecosystem, Impact
Analysis, Project Memory) -- no LLM, no embeddings, no AI API, no hidden
weighting. `api.py` lives inside the package itself, matching Sprint
C9's own deviation from the `app/routers/` convention.

**Canonical `ExecutiveDecision`** (`models.py`): `generated_at,
recommended_project, decision_score, confidence, reason,
expected_benefit, estimated_effort, estimated_duration,
blocking_projects, projects_unblocked, commercial_value, technical_value,
risk, dependencies, today_plan, expected_result, evidence, limitations`.

**Scoring** (`scoring.py`): a fixed, additive, fully-documented point
table -- never a learned/hidden weighting. Nine contributors, each a pure
function returning `(points, reason | None)`:

| Contributor | Points | Source |
|---|---|---|
| Operational Intelligence priority | priority × 0.4 (max 40) | Sprint C6 |
| Business value / launch-readiness | 10-25, +15 bonus | `ProjectContext.business_value` / OI's "Consider shipping/launching" |
| Projects unblocked | 5 each, capped at 15 | Project Ecosystem `dependents_of` |
| Already blocking dependents | +10 | Project Ecosystem `blocks_of` |
| Impact Analysis risk | 2-15 by level | Sprint C9 `overall_risk` |
| Pending work recorded | +5 | Project Memory's own `_pending_work` |
| Recent activity / staleness | +5 / -5 | `ProjectContext.latest_activity` |
| Project health score | health × 0.1 (max 10) | `ProjectContext.health_score` |
| Paused/blocked status | -20 / -15 | `ProjectContext.status` |

Every non-zero contribution is named in `evidence`, in the fixed order
the function evaluates them above -- a score is always reconstructable
by re-reading `scoring.py` top to bottom, never a black box. Stale
Discovery data (`workspace.get_freshness().is_stale`) discounts
*confidence*, never the score itself.

**Conflict resolution** (`service._sort_key`): every adopted project is
scored once and sorted by `(decision_score desc, health_score desc,
canonical_project_id asc)` -- a total order with no ties possible, ever.

**Today's Plan** (`planner.py`): a single deterministic step for the
recommended project. `"09:00"` is a fixed label, not a real-clock
computation -- no scheduling engine, no calendar integration. Estimated
effort/duration come from a static keyword lookup over the recommended
action's own title, the same convention
`operational_intelligence.models.expected_benefit_for` already
established.

**No duplicate logic**: reuses `all_project_contexts`, `get_operational_
intelligence`, `compute_relationships`/the Project Ecosystem graph
(`dependents_of`/`blocks_of`/`dependencies_of`), and `get_impact_
analysis` exactly once per request -- each threaded through as an
optional parameter, the same "compute once at the outermost caller"
pattern established across Sprints C7.1/C8/C9. Pending Work and Next
Action text are not re-derived either: `app.project_memory.service`'s own
`_pending_work`/`_next_action_output` functions are imported and called
directly.

**Consumers**:

- **Mission Control** -- `GET /mission-control` gained
  `executive_decision`/`ranked_projects` fields, computed inside the same
  `request_scope()` that already collapses the shared-assets filesystem
  walk to once per request. The frontend now leads with a "TODAY" card
  (recommended project, reason, expected benefit, estimated effort/
  duration, next action, expected result, evidence) and a "Portfolio
  Ranking" section (every adopted project, ranked, each with its own top
  reasons) above the pre-existing operational cards, which are now
  supporting information.
- **Explorer search** -- a new result type, `"Executive Decision"`:
  searching `"today"`/`"decision"`/`"recommend"`/`"priority"`/`"focus"`/
  `"next"`, or the recommended project's own name, surfaces one card
  summarizing the current decision.

**Two real bugs found and fixed**: (1) the first Mission Control wiring
placed the new `get_executive_decision` call just after the existing
`request_scope()` block closed, so Executive Decision's own `compute_
relationships` call re-walked the filesystem for shared assets once per
adopted project instead of reusing the single walk already collapsed --
caught immediately by the pre-existing
`test_no_double_asset_walk_per_project_per_request` regression test;
fixed by moving the call inside the shared scope. (2) Live browser
verification found the frontend's `RESULT_TYPE_ORDER` array (Explorer's
render-order list, separate from the backend's `RESULT_TYPES`) had never
been updated for Sprint C8/C9's `"Ecosystem Relationship"`/`"Impact"`
result types either -- both had been silently un-renderable in the UI
since those sprints shipped; fixed by adding all three missing types
together.

**Performance**: reuses `all_project_contexts`/Operational Intelligence/
`compute_relationships`/Impact Analysis exactly once per request;
Executive Decision's own scoring/ranking/planning logic adds ~2ms on top
(profiled on the real workspace). End-to-end latency is dominated by the
pre-existing `all_project_contexts` (~750ms)/`compute_relationships`
(~570ms) costs already documented in the C6/C8 reports -- the brief's
500ms target is not met on this real, ~18-project workspace as a result,
an inherited rather than introduced cost.

| Method | Path                | Description |
|--------|----------------------|--------------|
| GET    | `/executive-decision` | The current `ExecutiveDecision` plus `ranked_projects` (the full portfolio ranking) |

**Known limitations**: no scheduling engine or calendar integration (by
design); estimated effort/duration are a static per-keyword lookup, not a
per-project estimate; the 500ms performance target is not met on this
real workspace (see Performance above); Today's Plan is always exactly
one step, never a multi-item day plan. See `docs/product/DECISIONS.md`
for the full reasoning.

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
    services/                       # Cross-cutting services that own no persistence (v1.2)
      launcher.py                      # AI Launcher: prompt assembly + tool-to-URL resolution
      resume.py                        # Resume Engine (v1.4): continuation prompt from a session's latest snapshot
    routers/
      health.py, projects.py, search.py, knowledge.py   # Milestone 1 API (unchanged)
      ui.py                                                # Dashboard page + /ui/recent, /ui/timeline
      pi/                                                    # Project Intelligence routers, namespaced /pi
        workspaces.py, projects.py, collections.py,
        capabilities.py, dependencies.py, health.py,
        ai_workspace.py                                          # AI Workspace (v1.3): saved Claude/ChatGPT/Gemini links
        ai_sessions.py                                             # AI Sessions + Snapshots + Resume + Timeline (v1.4)
      advisor.py                                               # Advisor API, namespaced /advisor
      advisor_search.py                                         # Advisor Search API (Sprint 6), namespaced /advisor/search
      graph.py                                                  # Knowledge Graph API, namespaced /graph
      imports.py                                                 # ChatGPT Conversation Importer + Explorer API, namespaced /import
      extraction.py                                               # Knowledge Extraction API, namespaced /extraction
      conversation_graph.py                                        # Knowledge Graph (Sprint 5) API, namespaced /conversation-graph
      settings.py                                                   # Settings API (Sprint 8), namespaced /settings
      session.py                                                     # Daily Session API (ROLE OS Dashboard MVP), namespaced /session
      launcher.py                                                     # AI Launcher API (v1.2), namespaced /launcher
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
