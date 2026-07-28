# Architecture

This is a condensed, whole-repository view of how ROLE OS is built and how
its parts interact. It describes only what exists in this codebase today —
for full depth on any one part, follow the links at the end of each
section. The original, most detailed design documents live under
[`docs/architecture/`](docs/architecture/); this file is the release-facing
summary of the same system.

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
| Knowledge API | `/`, `/search`, `/projects`, `/knowledge/{id}`, `/ui/*` | `role_os.db` (Builder-generated, read-only) | Milestones 1–3 |
| Project Intelligence | `/pi/*` | own SQLite DB | Epic 1 |
| AI Advisor | `/advisor/*` | own SQLite DB (reads Builder + Project Intelligence DBs) | Epic 2 |
| Knowledge Graph | `/graph/*` | none — computed on demand from the three DBs above | Epic 3 |
| ChatGPT Importer + Conversation Explorer | `/import/*` | own SQLite DB | Sprint B1 / B1.5 |
| Knowledge Extraction | `/extraction/*` | own SQLite DB (reads the Importer DB) | Sprint 4 |
| second Knowledge Graph | `/conversation-graph/*` | none — computed on demand from the Importer + Extraction DBs | Sprint 5 |
| Advisor Search | `/advisor/search/*` | none — reads the Importer + Extraction DBs | Sprint 6 |
| Settings | `/settings/*` | none — reads all of the above, writes nothing new | Sprint 8 |
| Command Center UI | served at `/`, hash-routed client-side | none — pure presentation over every API above | Epic 4 |

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

## No implementation details beyond what exists

This document intentionally does not describe planned features, a
message queue, caching layer, authentication system, or multi-user
support — none of those exist in this codebase. See
[`docs/architecture/07_ROADMAP.md`](docs/architecture/07_ROADMAP.md) for
documented extension seams (not commitments), and
[`RELEASE_NOTES_v1.0.md`](RELEASE_NOTES_v1.0.md) for known limitations.

## Where to go next

- [`docs/architecture/03_ARCHITECTURE.md`](docs/architecture/03_ARCHITECTURE.md) — the original, most detailed architecture write-up.
- [`docs/architecture/04_DATA_MODEL.md`](docs/architecture/04_DATA_MODEL.md) — concrete schemas per domain.
- [`dashboard/README.md`](dashboard/README.md) — every API endpoint, request/response shape, and domain-by-domain detail.
- [`builder/README.md`](builder/README.md) — the Builder's extraction pipeline and output layout.
