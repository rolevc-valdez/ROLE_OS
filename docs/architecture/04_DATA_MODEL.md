# 04 — Data Model

ROLE OS has three persisted stores plus one computed-on-demand layer. This
document describes the entities in each.

## 1. Knowledge database (`role_os.db`, Builder-generated)

Produced by `builder.py`, read-only from the dashboard's perspective, and
regenerated wholesale on every Builder run. Table: `knowledge_cards`.

Each **Knowledge Card** (one per ChatGPT conversation) has:

| Field | Produced by |
|---|---|
| `summary` | `extractors/summary.py` |
| `decisions`, `deliverables` | `extractors/decisions.py` |
| `todos` (open TODOs) | `extractors/todos.py` |
| `prompts` (the user's own messages, in order) | `extractors/prompts.py` |
| `people`, `applications`, `vendors`, `urls`, `files`, `tags`, project classification | `extractors/entities.py` |
| `related_conversations` (up to 5, weighted overlap of project/tags/people/applications) | `extractors/relationships.py`, corpus-level second pass |

`assets` is kept as a deprecated alias for `files` for backward
compatibility. Alongside the database, the Builder also writes
human-readable cross-reference indexes: `PROJECTS.json`, `PEOPLE.json`,
`APPLICATIONS.json`, `VENDORS.json`, `TAGS.json`, `TIMELINE.json`, and
`00_SYSTEM/MASTER_INDEX.md`.

## 2. Project Intelligence database (`ROLE_OS_PROJECTS_DB_PATH`, dashboard-owned)

Schema and default workspaces (`Personal`, `Kontoor`, `Unger`, `Products`,
`Ideas`, `Library`) are created automatically on first use.

**Workspace**: `id`, `name`, project count (derived).

**Project**: `id`, `workspace`, `name`, `description`, `status`,
`health_score`, `priority`, `tags`, `owner`, `created_at`, `updated_at`,
plus these collections:

- `notes`, `decisions`, `todos`, `deliverables`, `assets`, `prompts` — free
  collection items
- `conversations` — linked knowledge-base conversation ids (join to the
  Knowledge database)
- `related_projects` — links to other Projects
- `capabilities` — capabilities this project **exposes**
- `dependencies` — other Projects this project **depends on**

**Capability**: exposed by one project, consumable by others (e.g. `ROLE
Master` exposes "Brand Identity", `SUPER FACIL` consumes it). Queryable
globally (`/pi/capabilities?q=`) and per-capability by consumer
(`/pi/capabilities/{id}/consumers`).

**Dependency**: a directed edge Project → Project, queryable in both
directions — `/pi/projects/{id}/dependencies` (what it depends on) and
`/pi/projects/{id}/dependents` (what depends on it, reverse lookup).

**Health Score**: a 0-100 value stored on the Project, recomputed by
combining independent signals (see `app/projects/health/`):

| Signal | File | Measures |
|---|---|---|
| Activity | `activity.py` | recency of the project's own last update |
| TODOs | `todos.py` | open TODO count |
| Decisions | `decisions.py` | unresolved (pending) decisions |
| Deliverables | `deliverables.py` | missing (undelivered) deliverables |
| Conversations | `conversations.py` | recency of linked knowledge-base conversations |
| Commits | `commits.py` | recent commits — implemented but always `None`/unavailable; no git integration wired up yet, so it's excluded from scoring rather than penalizing every project |

Weights are renormalized over whichever signals are actually present.

## 3. Advisor database (`ROLE_OS_ADVISOR_DB_PATH`, dashboard-owned)

Written only by the recommendation engine; reads (never writes) the
Knowledge and Project Intelligence databases.

**Recommendation**: `id`, `project_id`, `workspace`, `title`, `summary`,
`recommendation_type`, `priority_score`, `confidence_score`, `reason`,
`evidence`, `suggested_action`, `estimated_effort`, `impact`,
`created_at`, `expires_at`, `dismissed`, `completed`.

Deduplicated by `(project_id, recommendation_type)`: a new row is only
inserted if no existing row for that key is still "live" (`expires_at` in
the future). Dismissed/completed rows are never overwritten and continue
to suppress regeneration until they expire; nothing is ever deleted, so
the table doubles as a full history/audit log.

Eight rules (`app/advisor/rules/`) produce `recommendation_type` values:
`update_stale_project`, `review_risk` (also from `critical_health`),
`continue_project`, `finish_deliverable`, `resolve_todo`,
`unblock_dependency`, `review_decision`, `reuse_capability`. See
[[03_ARCHITECTURE]] and `dashboard/README.md` for the full rule table.

## 4. Knowledge Graph (computed, no database)

Not a persisted store — `app/graph/engine.py::build_graph()` assembles it
fresh from the three databases above on every `/graph/*` request. See
`app/graph/models.py` for the canonical definitions.

**12 node types**: `Project`, `KnowledgeCard`, `Person`, `Application`,
`Vendor`, `Capability`, `Workspace`, `Decision`, `Deliverable`, `Prompt`,
`Asset`, `Conversation`.

Every node has a stable, globally unique id `<type>:<raw-id>` (e.g.
`project:1a2b3c`). Entity nodes referenced only by name (`Person`,
`Application`, `Vendor`) are deduplicated by a slugified name.

**12 relationship types**:

| Type | Meaning |
|---|---|
| `DEPENDS_ON` | Project depends on Project (from Project Intelligence `dependencies`) |
| `UNBLOCKS` | Precomputed reverse of `DEPENDS_ON` |
| `IMPLEMENTS` | Project exposes/implements a Capability |
| `USES` | Project consumes a Capability, or uses an Application/Vendor |
| `SHARES_CAPABILITY` | Consumer Project ↔ provider Project, precomputed convenience edge |
| `PROVIDES` | Vendor provides an Application (co-occurrence in the same card) |
| `REFERENCES` | Project → its own Decision/Deliverable/Prompt/Asset; KnowledgeCard → a mentioned Asset |
| `RELATED_TO` | Project ↔ related Project; KnowledgeCard ↔ KnowledgeCard (via `related_conversations`) |
| `BELONGS_TO` | Project → Workspace; KnowledgeCard → Project |
| `CREATED_BY` | Project → owning Person |
| `MENTIONS` | KnowledgeCard → mentioned Person/Application/Vendor |
| `GENERATED_FROM` | KnowledgeCard → source Conversation |

## Entity relationship summary

```
Workspace 1───* Project
Project *───* Project        (RELATED_TO, DEPENDS_ON/UNBLOCKS, SHARES_CAPABILITY)
Project 1───* Decision, Deliverable, Prompt, Asset, Note, TODO  (REFERENCES)
Project 1───* Capability (IMPLEMENTS)         Capability *───* Project (USES, consumer side)
Project *───* Conversation (BELONGS_TO)  ──▶  Conversation 1───1 KnowledgeCard (GENERATED_FROM)
KnowledgeCard *───* Person / Application / Vendor  (MENTIONS)
Vendor *───* Application  (PROVIDES, co-occurrence)
Project 1───1 Person  (CREATED_BY, owner)
Project 1───* Recommendation  (Advisor DB, not a graph edge — looked up on demand for impact analysis)
```

## Where to go next

- [[03_ARCHITECTURE]] — how these stores are wired into the running system.
- [[05_UI_GUIDELINES]] — how this data is presented in the Command Center.
