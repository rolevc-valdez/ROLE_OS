# Architecture

This is a condensed, whole-repository view of how ROLE OS is built and how
its parts interact. It describes only what exists in this codebase today —
for full depth on any one part, follow the links at the end of each
section. The original, most detailed design documents live under
[`docs/architecture/`](docs/architecture/); this file is the release-facing
summary of the same system.

**Two layers, both real, both currently running:** the sections
immediately below ("Infrastructure" through "Settings") describe the
original v1.x Knowledge/Project Intelligence layer, built around a
ChatGPT export. **"Role OS 2.0" (further down this file)** is a second,
independent layer built around your own project *folders* instead —
Discovery, Workspace Adoption, Project Context, Resume Work, Operational
Intelligence, Executive Decision, and Mission Control (now the canonical
landing page). Neither layer replaces the other; they share one Command
Center UI shell and one FastAPI process. If you're looking for what a
fresh user or AI session actually sees first today, skip to "Role OS
2.0" below — this is also the layer under active development (see
`CURRENT_STATE.md`/`NEXT_ACTIONS.md`).

## Infrastructure

ROLE OS has two halves that never run as the same process:

- **Builder** (`/builder`) — an offline CLI, standard-library only, no
  service, no network calls. It takes a ChatGPT conversations export and
  produces a `ROLE_KNOWLEDGE_OS` folder plus a SQLite database
  (`role_os.db`).
- **Dashboard** (`/dashboard`) — a FastAPI application that reads the
  Builder's database (read-only, from its perspective) and layers seven
  additional domains on top, each owning its own SQLite file or computing
  fresh from the others on every request. No domain writes to a database
  it doesn't own, and nothing above the Builder ever writes back into
  `role_os.db`.

| Domain | Namespace | Storage | Introduced |
|---|---|---|---|
| Knowledge API | `/search`, `/projects`, `/knowledge/{id}`, `/ui/*` | `role_os.db` (Builder-generated, read-only) | Milestones 1–3 |
| Project Intelligence | `/pi/*` | own SQLite DB | Epic 1 |
| AI Advisor | `/advisor/*` | own SQLite DB (reads Builder + Project Intelligence DBs) | Epic 2 |
| Knowledge Graph | `/graph/*` | none — computed on demand from the three DBs above | Epic 3 |
| ChatGPT Importer + Conversation Explorer | `/import/*` | own SQLite DB | Sprint B1 / B1.5 |
| Knowledge Extraction | `/extraction/*` | own SQLite DB (reads the Importer DB) | Sprint 4 |
| second Knowledge Graph | `/conversation-graph/*` | none — computed on demand from the Importer + Extraction DBs | Sprint 5 |
| Advisor Search | `/advisor/search/*` | none — reads the Importer + Extraction DBs | Sprint 6 |
| Settings | `/settings/*` | none — reads all of the above, writes nothing new | Sprint 8 |
| Command Center UI | hash-routed client-side; `/` itself now serves Mission Control (Role OS 2.0, below), not this layer's own Home view | none — pure presentation over every API above | Epic 4 |

No external services are required anywhere in this stack — no Postgres, no
Redis, no message queue, no external AI/LLM API.

## Importer

**`dashboard/app/imports/`** — a dashboard-owned pipeline for bringing
ChatGPT conversation exports in directly, without regenerating the whole
Builder-generated knowledge base. Validates the export, normalizes each
conversation (title, timestamps, message count, roles, content),
fingerprints it for deduplication, and persists it plus a per-import run
record. Reachable via the UI (Knowledge page's import panel), the API
(`POST /import/chatgpt`), or the CLI (`scripts/import_chatgpt.py`) — all
three call the same `run_import()` function, so they can never drift.
Explicitly does not do AI extraction, project matching, or graph
inference; that is layered on afterward by the Extraction and Knowledge
Graph domains below.

## Explorer

The Conversation Explorer is a UI-only page (no domain of its own) over
the Importer's data: search/filter/sort/paginate imported conversations
(`GET /import/conversations`), inspect one in full detail including its
message timeline, export it as JSON, or delete it. Its "Knowledge" section
is where Extraction is triggered per conversation, and its detail view
links out to the (Sprint 5) Knowledge Graph.

## Extraction

**`dashboard/app/extraction/`** — deterministic, rule-based pattern
matching (regex/keyword-line matching, no AI/LLM call) that pulls seven
object types — Project, Person, Task, Decision, Idea, Document, Asset —
out of an imported conversation's content. Reads from the Importer's
database, writes to its own. Deduplicated per-conversation by a content
fingerprint, so re-running extraction is always safe: it never creates
duplicates and never silently deletes something you kept (deletion is
always explicit).

## Knowledge Graph

Two independent, computed-on-demand graphs — neither is a persisted
graph database:

- **Epic 3's graph** (`dashboard/app/graph/`, `/graph/*`) — 12 node types,
  12 relationship types, built fresh from the Builder, Project
  Intelligence, and Advisor databases on every request. Supports
  neighbor traversal, shortest-path, and impact analysis.
- **Sprint 5's graph** (`dashboard/app/conversation_graph/`,
  `/conversation-graph/*`) — 8 node types, one `contains` relationship,
  built fresh from the Importer and Extraction databases. Deliberately
  kept separate from Epic 3's graph rather than merged into it, since the
  two pipelines' vocabularies collide on type names but represent
  different data (see [`docs/product/DECISIONS.md`](docs/product/DECISIONS.md)).

Both follow the same principle: recompute from the source-of-truth
databases on every read, rather than maintaining a duplicate copy that
could drift out of sync.

## Advisor

**`dashboard/app/advisor/`** — two independent capabilities under one
package:

- **Recommendation engine** (`engine.py`, `rules/`, `scoring.py`,
  `narrative.py`, `db.py`) — eight independent, deterministic rules
  evaluate every Project's Health Score, TODOs, deliverables, decisions,
  and dependencies to recommend what to work on next, each with a
  `reason`, `evidence`, `suggested_action`, and `impact` (fully
  explainable, no black box). Recommendations persist in their own
  SQLite database and are deduplicated by `(project, recommendation_type)`.
- **Advisor Search** (`search.py`, `search_models.py`, Sprint 6) — plain
  keyword/partial-match search across imported conversations and
  extracted objects, a sibling capability with a different data source
  and no shared logic with the recommendation engine above.

`AdvisorNarrativeProvider` (`narrative.py`) is a designed seam for a
future LLM-backed provider to improve wording without touching the rule
logic, scoring, or persistence — not implemented in this release.

## Dashboard (executive summary page)

The Dashboard *page* (Sprint 7, not to be confused with the `/dashboard`
directory that holds the whole FastAPI app) is a UI-only view: ten summary
cards, recent activity, and system status, all read verbatim from
existing endpoints (`GET /import/metrics`, `GET /extraction/recent`,
`GET /extraction/runs`) — no new calculation, no new storage.

## Settings

**`dashboard/app/routers/settings.py`** (Sprint 8) — a single additive
router that aggregates configuration and status information that already
exists across every domain above: database paths, live counts, Knowledge
Graph status, and version/commit/license info. No new persistence model.
Export downloads the current configuration as JSON; import validates an
uploaded file and previews which environment variables it maps to, but
never applies it to the running process (there is no mechanism to safely
mutate a live server's environment, by design). Maintenance actions:
force a fresh Knowledge Graph rebuild, or clear the in-memory settings
cache so an updated environment variable takes effect without a restart.

## How it all interacts

```
ChatGPT export (.zip)
        │
        ▼
   builder/builder.py  ──▶  extractors/ pipeline
        │
        ▼
  role_os.db  (read-only from the dashboard's perspective)
        │
        ├──▶ Knowledge API ──▶ Command Center UI (Home, Knowledge, Project Detail)
        │
        ▼
  Project Intelligence DB (mutated via /pi/*)
        │
        ├──▶ Health Score engine
        ▼
  AI Advisor DB (written only by the recommendation engine)
        │
        ▼
  Knowledge Graph (Epic 3, computed fresh, no DB) ──▶ Graph page

     ── separately ──

  Importer DB (written via /import/*)
        │
        ▼
  Extraction DB (written via /extraction/*, reads Importer DB read-only)
        │
        ▼
  second Knowledge Graph (Sprint 5, computed fresh, no DB) ──▶ Knowledge Graph page
        │
        ▼
  Advisor Search (reads Importer + Extraction DBs) ──▶ Advisor page's Search Knowledge

     ── on top of everything above ──

  Settings (reads every domain's config/status, writes nothing new) ──▶ Settings page
  Command Center UI (static HTML/CSS/JS) ──▶ every page above, via fetch() only
```

Every arrow above is a read, except the two explicitly labeled "written
via" — the Command Center UI itself never writes anything directly; every
mutation goes through the `/pi/*` or `/advisor/*` (dismiss/complete) API
it's already built on.

## Role OS 2.0

A second, independent chain, built around your own project *folders*
rather than a ChatGPT export. Phase 1 (`docs/PHASE_1_COMPLETION.md`)
built and verified the core; Phase 2 (`docs/ROLE_OS_2_PHASE_2_PLAN.md`,
in progress — see `CURRENT_STATE.md` for exactly which task) extends it.

| Domain | Namespace | Storage | Introduced |
|---|---|---|---|
| Discovery Engine | CLI (`python -m app.discovery`) + internal, called by Workspace | none — read-only filesystem scan, no DB of its own | Phase 1, Sprint 1; Multi-Root Discovery, Phase 2 Task 2.1 |
| Workspace Adoption | `/workspace/*` | own SQLite DB (`role_os_workspace.db`): cached scan + adopted/ignored overlay | Phase 1, Discovery Engine Sprint 2+ |
| Project Context | no dedicated router — a shared internal shape every project-facing page reads through | none — computed fresh from Workspace/Assets/PI on every read | Sprint C1/C1B |
| Project Memory | composed into Project Context, no dedicated router | none | (part of Project Context) |
| Assets OS | `/assets/*` | own SQLite DB (`role_os_assets.db`): cached metadata + overrides, never file bytes | Sprint C4 |
| Project Ecosystem | `/ecosystem/*` | own SQLite DB (`role_os_ecosystem.db`): manual relationship overrides only | Sprint C8 |
| Impact Analysis | composed into Project Ecosystem/Project Memory output | none — computed on demand | Sprint C9 |
| Operational Intelligence | composed into Mission Control/Project Context, no dedicated router | none — the one canonical recommendation ranking, computed fresh | Sprint C6 |
| Executive Decision | composed into Mission Control, no dedicated router | none — layered on Operational Intelligence's output | Sprint C10 |
| Mission Control | `/mission-control` | none — pure composition over every domain above | Sprint C5 |
| Daily Session | `/session/*` | own SQLite DB (`role_os_session.db`) | ROLE OS Dashboard MVP |

No external services here either — same SQLite-only, no-external-AI-API
rule as the v1.x layer above.

### Discovery Engine → Workspace Adoption

Discovery (`dashboard/app/discovery/`) is strictly read-only: given one or
more root folders, it scans direct children (and, selectively, one level
deeper into non-self-contained "container" folders), classifies each
(Software Project / Documentation Project / Mixed Project / Non-project /
excluded), and computes a Health Score and move-risk. It never writes
inside a scanned tree and never decides anything about adoption.

**Multi-Root Discovery** (`app/discovery/roots.py`, Phase 2 Task 2.1):
`ROLE_OS_DISCOVERY_ROOTS` (comma-separated, optional) lets more than one
root be scanned in one request. Each configured root is validated
(exists, is a directory) and deduplicated (exact/case/slash duplicates
and nested roots dropped, keeping the outer one) before scanning; results
merge into one cached list, deduplicated by the same `discovery_id`
(`app/discovery/identity.py`, a hash of the folder's absolute path) every
other Workspace lookup already uses. With no multi-root configuration,
behavior is identical to the original single-`ROLE_OS_DISCOVERY_ROOT`
model. See `docs/PHASE_2_MULTI_ROOT_DISCOVERY.md`.

**Discovery is never adoption.** `app/workspace/service.py` caches the
scan and layers a small, explicit user overlay on top
(`adopted`/`ignored`/priority/business value/status/tags/notes) — a
discovered folder only becomes a first-class ROLE OS Project
(bridged into the v1.x Project Intelligence DB via
`app/workspace/identity.py`, so AI Sessions/Timeline/Resume Work work
immediately) when a user explicitly adopts it, one at a time, on the
Workspace page or via `POST /workspace/{id}/adopt`. Nothing in Discovery,
Multi-Root Discovery, or a rescan ever adopts anything automatically.

### Project Context, Resume Work, and the recommendation chain

`app/project_context/builder.py` is the one canonical "what is this
project" shape (health, next action, latest AI session/snapshot, resume
state) — every page that shows project information (Mission Control,
Projects, Workspace, Cockpit) reads through `all_project_contexts()`/
`build_project_context()` instead of re-assembling its own subset, so
they can never disagree with each other. It only ever considers **adopted**
projects (`list_enriched_top_level_projects(adopted_only=True)`) — a
project that Discovery found but nobody adopted is invisible to this
entire chain, by design, regardless of how many Discovery roots are
configured.

`app/workspace/resume.py` (Resume Work) builds a ready-to-paste
continuation prompt from a project's own real, canonical history
(latest snapshot, pending work, next action, latest AI session) — not a
generic template and not a second "what was I doing" tracker.

`app/operational_intelligence` ranks every adopted project by a
deterministic, evidence-based score (health, staleness, business value,
commercial readiness, dependencies) — one canonical recommendation
engine, reused by Today's Focus, Needs Attention, Value Signal, and the
Daily Session suggestion (four *views* over one already-sorted list, not
four separate rankings). `app/executive_decision` layers one more,
cheap pass on top to name a single "what to do today" pick, with its own
score, confidence, reason, and evidence — confidence is explicitly
discounted when the underlying Discovery scan is stale
(`data_freshness.is_stale`), never silently presented as equally fresh.

### Mission Control

`app/mission_control/service.py: build_mission_control()` is the single
`GET /mission-control` payload and **the canonical landing page** (served
at `/` and `/mission-control`) — pure composition, one filesystem walk
per request (`app.assets.service.request_scope()`), zero new ranking
logic of its own. It answers, in this order: Where I Left Off (Primary
Focus, reusing Home's own `suggested_project_to_continue` + Resume Work),
What Matters Now (Executive Decision), What's Next (Today's Focus) —
followed by supporting sections (Portfolio Ranking, Since Last Time,
Needs Attention, Daily Session, Value Signal, Portfolio). Directly
re-verified against live canonical data in Phase 2's Mission Control
Daily-Use Gap Check (`docs/PHASE_2_MISSION_CONTROL_DAILY_USE_REVIEW.md`):
all four daily questions score CLEAR, with zero required clicks to see
any answer and exactly one click to act on it.

The original v1.x "Home" page (`#/home`) still exists as a route, but its
own hash now renders Mission Control (`dashboard/README.md`, "Home
(superseded by Mission Control)") — there is no second, competing landing
experience.

### Runtime data

Two canonical runtime roots, both anchored to the repository root
regardless of launch directory (`app/config.py: Settings.repo_root`,
derived from `__file__`, never the process's current working directory):

- **`var/role_os/`** — the v1.x Knowledge/Project Intelligence/Advisor/
  Imports/Extraction family.
- **`var/role_os_dashboard/`** — the Role OS 2.0
  Workspace/Session/Assets/Ecosystem family.

Full inventory and provenance evidence: `docs/RUNTIME_DATA_MAP.md`. Every
dashboard-owned path is independently overridable via its own
`ROLE_OS_*_PATH` environment variable — see `dashboard/README.md`'s
Configuration table for the complete, current list, including
`ROLE_OS_DISCOVERY_ROOT(S)`.

### Freshness and fallback honesty

Every recommendation that depends on a Discovery scan
(`data_freshness.is_stale`, computed from `last_scan` age) or an optional
external file (e.g. `ROLE_OS_ECOSYSTEM_DECISION_LOG_PATH`) discloses that
fact directly in the UI (a staleness note on the Executive Decision card,
a page-level "Stale discovery data" banner, a "Fallback snapshot" badge)
rather than silently presenting old or substitute data as if it were
live and current.

## No implementation details beyond what exists

This document intentionally does not describe planned features, a
message queue, caching layer, authentication system, or multi-user
support — none of those exist in this codebase. It also does not
describe an explicit-project-registration Discovery mechanism (distinct
paths a user manually adds, independent of any scan root) — this was
evaluated and deliberately deferred, not built (`docs/ROLE_OS_2_PHASE_2_PLAN.md`
§6; a real, evidenced case for one is noted in
`docs/PHASE_2_MISSION_CONTROL_DAILY_USE_REVIEW.md`'s "Discovery /
Isolated Repository Note", but it remains unimplemented). See
[`docs/architecture/07_ROADMAP.md`](docs/architecture/07_ROADMAP.md) for
documented extension seams (not commitments), and
[`RELEASE_NOTES_v1.0.md`](RELEASE_NOTES_v1.0.md) for known limitations
in the v1.x layer.

## Where to go next

- [`CURRENT_STATE.md`](CURRENT_STATE.md) / [`NEXT_ACTIONS.md`](NEXT_ACTIONS.md) — what's true *right now*, and what's next. Read these before any historical report below.
- [`docs/architecture/03_ARCHITECTURE.md`](docs/architecture/03_ARCHITECTURE.md) — the original, most detailed v1.x architecture write-up.
- [`docs/architecture/04_DATA_MODEL.md`](docs/architecture/04_DATA_MODEL.md) — concrete v1.x schemas per domain.
- [`docs/PHASE_1_COMPLETION.md`](docs/PHASE_1_COMPLETION.md) — how and when the Role OS 2.0 core (Discovery, Workspace, Mission Control, Resume Work) was built and verified.
- [`docs/RUNTIME_DATA_MAP.md`](docs/RUNTIME_DATA_MAP.md) — the full current runtime-data inventory for both layers.
- [`docs/PHASE_2_MULTI_ROOT_DISCOVERY.md`](docs/PHASE_2_MULTI_ROOT_DISCOVERY.md) — Multi-Root Discovery's design and validation.
- [`dashboard/README.md`](dashboard/README.md) — every API endpoint, request/response shape, environment variable, and domain-by-domain detail, both layers.
- [`builder/README.md`](builder/README.md) — the Builder's extraction pipeline and output layout.
