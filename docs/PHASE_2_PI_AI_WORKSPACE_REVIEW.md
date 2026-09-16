# Role OS 2.0 — PI AI Workspace Review

## Objective

Resolve the long-standing REVIEW flag (`CURRENT_STATE.md` Open Issue #5, deferred since Phase 1): is `pi_ai_workspace` (v1.3) a distinct active concept from `pi_ai_sessions`/`ai_session_snapshots` (v1.4), a superseded legacy table, or a duplicate/overlapping implementation? Analysis only — no deletion, migration, rename, or code change performed.

## Concepts Inspected

Searched the whole repository for every pattern named in this task's brief (`pi_ai_workspace`, `pi_ai_workspaces`, `pi_ai_session`, `pi_ai_sessions`, `ai_workspace`, `ai_session`, `ai_session_snapshots`). Three real database tables exist, all in `role_os_projects.db` (Project Intelligence's own database — no separate `pi_ai_workspace`/`pi_ai_sessions` SQLite files; the `pi_` prefix in this task's naming refers to the `/pi/*` API namespace both live under, not separate storage):

- **`ai_workspace`** (v1.3) — one row per project, one saved conversation URL per assistant (Claude/ChatGPT/Gemini), a role, a preferred model, a last-opened timestamp.
- **`ai_sessions`** (v1.4 "Context Engine") — a collection, many rows per project, one per assistant conversation (title, assistant, conversation URL, role, preferred model, status, favorite/current flags, timestamps).
- **`ai_session_snapshots`** — child of `ai_sessions` (`session_id` FK), a point-in-time record of a session's accomplishments/blockers/pending work/next prompt/decisions/summary.

## Dependency Map

| Layer | `ai_workspace` (v1.3) | `ai_sessions` / `ai_session_snapshots` (v1.4) |
|---|---|---|
| Router | `dashboard/app/routers/pi/ai_workspace.py` — `GET`/`PUT /pi/projects/{id}/ai-workspace`, `POST .../ai-workspace/open` | `dashboard/app/routers/pi/ai_sessions.py` — 11 routes: CRUD, set-current, open, snapshot create/list, resume, memory, timeline |
| Registered in `main.py`? | Yes (`app.include_router(pi_ai_workspace.router)`) | Yes (`app.include_router(pi_ai_sessions.router)`) |
| Service/db functions | `app/projects/db.py`: `get_ai_workspace`, `save_ai_workspace`, `touch_ai_workspace_last_opened` | `app/projects/db.py`: `create_ai_session`, `list_ai_sessions`, `update_ai_session`, `delete_ai_session`, `set_ai_session_current`, `touch_ai_session_last_used`, `create_ai_session_snapshot`, `list_ai_session_snapshots`, `get_latest_snapshot`, `get_ai_session_summary_for_project` |
| Models | `app/projects/models.py`: `AIWorkspace`, `AIWorkspaceSave`, `AIWorkspaceOpenRequest/Response` | `app/projects/models.py`: `AISession`, `AISessionSnapshot`, `AISessionResumeResult`, etc. |
| Tests | `test_ai_workspace_api.py` (165 lines), `test_ai_workspace_db.py` (92 lines), `test_ai_workspace_ui.py` (71 lines — proves the old UI card was deleted, backend preserved) | `test_ai_sessions_db.py`, `test_ai_sessions_api.py`, `test_ai_sessions_migration.py` (167 lines, migration-specific) |
| Frontend caller (`app.js`) | **None.** Zero `fetch`/`post` calls to `/pi/projects/{id}/ai-workspace*` anywhere in `app.js`; the only match is a comment documenting that the old UI card was replaced | Yes — the AI Sessions + Cockpit UI (v1.4) is the current Project Detail experience |
| Mission Control caller | No | Yes — via `app.project_context.builder` → `get_ai_session_summary` → `projects_db.list_ai_sessions`/`get_latest_snapshot` |
| Workspace/Resume Work caller | No | Yes — `app/workspace/resume.py` reads/writes exclusively through `list_ai_sessions`, `create_ai_session`, `update_ai_session`, `set_ai_session_current`, `touch_ai_session_last_used` |
| Project reconciliation (merge duplicates) | Yes — `app/projects/db.py` (~line 714): correctly migrates the single `ai_workspace` row (PK = `project_id`) when two projects merge, backfilling blank fields from the duplicate | Yes — `ai_sessions` rows are reassigned to the surviving project id |
| Documentation | `dashboard/README.md` still documents the v1.3 endpoints; `docs/product/DECISIONS.md` has two dedicated decision records (see below) | `dashboard/README.md`'s Mission Control/Workspace sections; `docs/architecture/13_PROJECT_UNIFICATION_SPRINT5_REPORT.md` |

## Data Model Comparison

| | `ai_workspace` | `ai_sessions` | `ai_session_snapshots` |
|---|---|---|---|
| Purpose | v1.3: one saved conversation link per assistant per project | v1.4: a full collection of assistant conversation sessions per project | v1.4: point-in-time progress record per session |
| Database | `role_os_projects.db` | same | same |
| Table | `ai_workspace` | `ai_sessions` | `ai_session_snapshots` |
| Primary key / identity | `project_id` (PK — **at most one row per project**) | `id` (UUID hex) | `id` (UUID hex) |
| Project relationship | `project_id REFERENCES projects(id)` | `project_id REFERENCES projects(id)` | via `session_id REFERENCES ai_sessions(id)` (indirect) |
| Write path | `save_ai_workspace`/`touch_ai_workspace_last_opened`, called only from `routers/pi/ai_workspace.py` | `create_ai_session`/`update_ai_session`/etc., called from `routers/pi/ai_sessions.py` **and** `app/workspace/resume.py` | `create_ai_session_snapshot`, called from `routers/pi/ai_sessions.py` and `app/workspace/resume.py` |
| Read path | `get_ai_workspace`, called only from its own router | `list_ai_sessions`/`get_latest_snapshot`, called from its own router, `app/project_context/builder.py`, `app/workspace/resume.py`, `app/dashboard/service.py`, `app/explorer/service.py`, `app/project_memory/service.py`, `app/project_ecosystem/detectors.py` | same breadth as `ai_sessions` |
| Lifecycle | Frozen since v1.4 shipped — one-time migration copied its data forward, then it was never written to by any new code path again (only by its own, still-functional API, if called directly) | Actively read/written by every current project-facing feature | Actively read/written wherever a session's progress needs recording |
| Row count (canonical, external `ROLE_KNOWLEDGE_OS\00_SYSTEM\role_os_projects.db`) | **0** | **6** | **1** |
| Row count (repo-root `var/role_os/role_os_projects.db`, fallback default — see note below) | **0** | **1** | **0** |
| Last known meaningful data | None found in either candidate database | 6 real sessions (external, canonical) | 1 real snapshot (external, canonical) |

**Note on which database is canonical:** `ROLE_OS_WORKSPACE_DIR` is set persistently on this machine (`docs/RUNTIME_DATA_MAP.md`) to `...\ROLE_KNOWLEDGE_OS`, making `ROLE_KNOWLEDGE_OS\00_SYSTEM\role_os_projects.db` the real, live data the launcher-driven application actually uses — 10 real projects, matching prior Phase 1 findings. The repo-root `var/role_os/role_os_projects.db` is the code's own fallback-when-unconfigured default (per `dashboard/app/config.py`); it holds a smaller, separate 5-project dataset, most plausibly created by an earlier session's direct `uvicorn` run without `ROLE_OS_WORKSPACE_DIR` set (as `RUNTIME_DATA_MAP.md` already flagged as a known risk for the CWD/config family — this is a *new* instance of the same class of issue, first observed during this task, since `var/role_os/` did not exist at all when `RUNTIME_DATA_MAP.md` was written on 2026-09-09). **Both were read in strict read-only SQLite mode (`?mode=ro` URI) for this review; both checksums were verified identical before and after inspection.** This divergence is disclosed as a new finding, not resolved here — it is a `var/role_os/` runtime-location question, unrelated to the `pi_ai_workspace`/`pi_ai_sessions` question this task was asked to resolve, and touching it is out of this task's scope.

## Runtime Usage

| Concept | Classification |
|---|---|
| `ai_workspace` (v1.3) | **REGISTERED BUT UNUSED** — router registered, backend fully functional and tested, zero frontend callers, zero callers from any other backend domain (Mission Control, Workspace, Resume Work, Project Context, Explorer, Dashboard, Project Ecosystem all searched — none reference it). Only self-referential: its own router/tests, plus the one-time migration and the project-reconciliation merge logic that correctly still accounts for it. |
| `ai_sessions` | **ACTIVE** — read and written by its own router, `app/workspace/resume.py` (Resume Work), `app/project_context/builder.py` (the canonical per-project shape every page reads), `app/dashboard/service.py`, `app/explorer/service.py`, `app/project_memory/service.py`, `app/project_ecosystem/detectors.py`. |
| `ai_session_snapshots` | **ACTIVE** — same breadth as `ai_sessions`; specifically the source of Mission Control's "Latest Snapshot"/"Saved Snapshot" and Resume Work's continuation prompt. |

This was traced through actual callers (`grep` for the real function names — `list_ai_sessions`, `get_latest_snapshot`, `get_ai_workspace`, etc. — not merely "is the router registered," per this task's explicit instruction not to infer usage from registration alone).

## Resume Work Relationship

Traced directly: `app/workspace/resume.py` (the Resume Work orchestration used by Mission Control's "Resume Work →" button and `POST /workspace/discovered/{id}/resume-work`) calls `projects_db.list_ai_sessions`, `projects_db.create_ai_session`, `projects_db.update_ai_session`, `projects_db.set_ai_session_current`, and `projects_db.touch_ai_session_last_used` — **exclusively**. It never calls `get_ai_workspace`, `save_ai_workspace`, or any `ai_workspace`-related function.

`app/project_context/builder.py`'s `get_ai_session_summary` (feeding "Where did I leave off?" on Mission Control's Primary Focus card, and the "Latest AI Session"/"Latest Snapshot" fields) also reads exclusively from `ai_sessions`/`ai_session_snapshots`.

**`ai_sessions`/`ai_session_snapshots` is the sole authoritative source for the "Where did I leave off?" / Resume Work chain. `ai_workspace` contributes nothing to it and never has, since v1.4 shipped.**

## Canonical Data Evidence

Read-only SQLite inspection (`sqlite3` URI mode `?mode=ro` — guarantees no write is possible at the driver level, not just by convention), against both candidate `role_os_projects.db` files. `PRAGMA integrity_check: ok` on both. Checksums (`sha256sum`) verified byte-identical before and after this task's entire inspection.

**Canonical (external, `ROLE_KNOWLEDGE_OS\00_SYSTEM\role_os_projects.db` — the real, `ROLE_OS_WORKSPACE_DIR`-selected data):**
- `ai_workspace`: **0 rows**
- `ai_sessions`: **6 rows**
- `ai_session_snapshots`: **1 row**
- `projects`: 10 rows
- `schema_migrations`: `['0001_ai_sessions_from_ai_workspace']` — the copy-forward migration has already run

**Repo-root fallback (`var/role_os/role_os_projects.db` — not this machine's real data, see note above):**
- `ai_workspace`: **0 rows**
- `ai_sessions`: **1 row**
- `ai_session_snapshots`: **0 rows**
- `projects`: 5 rows
- `schema_migrations`: same migration already run

No table is external/missing — both files have the full schema and the migration has already executed in both.

## Overlap Analysis

- **Same event/identity?** No genuine overlap in what's *currently* stored: `ai_workspace` is empty in every canonical database checked. There is no live data to compare for duplication — the question of "are they storing the same thing right now" resolves to "one of them is storing nothing."
- **Same project identity?** Both key off `projects.id` when populated, so if `ai_workspace` ever did hold data, it would refer to the same project rows `ai_sessions` does — no separate identity system.
- **Could one be derived from the other?** Already answered structurally: `ai_sessions` was *designed* to be `ai_workspace`'s replacement, and the one-time migration is precisely "derive `ai_sessions` rows from `ai_workspace` rows" — already executed, already tracked, already idempotent (`schema_migrations` prevents re-running).
- **Would removing either lose unique information?** Removing `ai_workspace` today would lose **no** unique information — its 0 rows in both real databases mean nothing is stored there that isn't either (a) also representable in `ai_sessions`, or (b) simply absent. Removing `ai_sessions`/`ai_session_snapshots` would be catastrophic — it is the sole real data source for 6 real sessions and 1 real snapshot, and the entire Resume Work/Mission Control chain depends on it.

## Classification

**B — LEGACY + CURRENT.**

This is not ambiguous. The codebase itself already says so, explicitly, in three independent places that all agree:
1. `app/projects/db.py` (~line 1313): *"AI Sessions (v1.4 Context Engine) — a collection... replacing AI Workspace's single record as the primary UI. The v1.3 `ai_workspace` table and functions above are left fully intact for backward compatibility... it is not kept in ongoing sync with them."*
2. `docs/product/DECISIONS.md`, "v1.4 keeps ai_workspace fully intact and copies its data forward, instead of migrating in place": *"Revisit only when a future task explicitly asks to retire `ai_workspace` for real."*
3. `dashboard/tests/test_ai_workspace_ui.py`'s own docstring: *"the old single-record card on the Project detail page was intentionally replaced... This is a UI-only change. The v1.3 backend contract... was explicitly required to keep working unmodified."*

Live evidence (zero rows in both candidate canonical databases, zero callers outside its own router/tests) confirms the design intent holds in practice, not just on paper.

## Recommendation

**DEPRECATE PI_AI_WORKSPACE** — formally mark it as deprecated (documentation and code comments only, in a future task), not remove it in this one.

This is well-evidenced, not a guess: zero live data anywhere, zero internal callers outside its own isolated router, a product decision record that already names the exact trigger for revisiting ("a future task explicitly asks to retire `ai_workspace` for real"), and a fully independent, already-proven replacement (`ai_sessions`) that the entire Resume Work/Mission Control chain already depends on exclusively. There is no consolidation *design* needed — there is nothing to merge, since there is no live data in `ai_workspace` to reconcile with `ai_sessions`. This is a deprecation candidate, not a duplication problem.

**No removal, deletion, or code change is performed in this task.** This section only documents what a future, separately-approved removal task would need to do.

## Removal / Compatibility Risks

If a future task is explicitly authorized to retire `ai_workspace`:

**Code that could eventually be removed:**
- `dashboard/app/routers/pi/ai_workspace.py` (the entire router)
- `app/projects/db.py`: `get_ai_workspace`, `save_ai_workspace`, `touch_ai_workspace_last_opened`, the `ai_workspace` `CREATE TABLE` block, and the project-reconciliation merge logic for `ai_workspace` (~line 714)
- `app/projects/models.py`: `AIWorkspace`, `AIWorkspaceSave`, `AIWorkspaceOpenRequest`, `AIWorkspaceOpenResponse`, `AIWorkspaceOpenResultItem`
- `app/main.py`: the `pi_ai_workspace` import and `app.include_router(pi_ai_workspace.router)` line
- `dashboard/tests/test_ai_workspace_api.py`, `test_ai_workspace_db.py`, `test_ai_workspace_ui.py` (the latter already tests *absence* of the old UI, so it would need re-scoping, not blind deletion)
- `dashboard/README.md`'s AI Workspace endpoint documentation
- The now-historical `_migrate_ai_workspace_to_sessions` function and its `MIGRATIONS` entry — **should NOT be removed** even if the table is dropped, unless every real deployment's migration has already run and is confirmed complete (removing a migration that hasn't run everywhere yet would silently strand pre-v1.4 data); this needs its own explicit check before any removal.

**Compatibility risks:**
- `/pi/projects/{id}/ai-workspace*` is a real, public, documented REST API. Nothing internal calls it, but an external client, script, or integration *could* — this cannot be verified from inside this repository. Any real removal should be versioned/announced, not silent.
- The `ai_workspace` table itself must not be dropped before confirming, on every real deployment (not just this machine), that the `0001_ai_sessions_from_ai_workspace` migration has actually run (`schema_migrations` contains it) — otherwise a database that skipped straight from a pre-v1.4 state would lose ungenerated `ai_sessions` rows it never got the chance to derive.

**Data that must be preserved:** None currently at risk (0 rows in both real databases inspected) — but this conclusion is specific to *this machine's* two known databases, not a guarantee for every possible deployment. A real removal task should re-verify row counts immediately before acting, not rely solely on this document's snapshot.

**Tests needed before removal:** A regression test asserting `0001_ai_sessions_from_ai_workspace` is present in `schema_migrations` (or that `ai_workspace` is genuinely empty) before the table is dropped in any given environment — this task does not add one, since no removal is happening.

## Exact Next Task

Phase 2 — Runtime Data Hygiene Bundle, remaining parts (a) delete the legacy `dashboard/var/role_os_dashboard/` copy and (b) fix ROLE MASTER's cosmetic status mismatch — both still **blocked on Role's explicit go-ahead** (`NEXT_ACTIONS.md`, "Blocked / Requires Role Decision"). If neither is approved, Phase 2's remaining closing steps apply instead (full-suite test run, control-file refresh to Phase 2 complete, a completion review mirroring `docs/PHASE_1_COMPLETION.md` — per `docs/ROLE_OS_2_PHASE_2_PLAN.md` §13).
