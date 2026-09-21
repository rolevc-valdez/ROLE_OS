# Role OS 2.0 — P3.2 Classification & Status Semantics

*Implements the smallest compatible extension approved after P3.1: `domain`, `client_name`, `kind`, and a recognised `completed` status. No UI, no Daily Command Center, no adoption, no runtime classification written.*

**Baseline:** `2b7e83f` (P3.1 complete, tree clean, no discrepancy with control files).

## Implemented Model

Extended the existing adoption overlay (`workspace.db: adopted_projects`) — the same table that already owns `priority`, `business_value`, `status`, `tags`, `notes`. No new table, no parallel persistence for tools, no TASK entity.

| Column | Type | Default for existing rows | Meaning |
|---|---|---|---|
| `domain` | `TEXT NULL` | `NULL` (= unclassified) | One of four fixed values |
| `client_name` | `TEXT NULL` | `NULL` | Only meaningful under `CLIENTES` |
| `kind` | `TEXT NOT NULL DEFAULT 'project'` | `'project'` | `project` or `tool` |

New module `dashboard/app/workspace/classification.py` holds the single vocabulary (`DOMAINS`, `KINDS`, `STATUS_COMPLETED`, normalisers, `is_completed_status`) so API, persistence and engines cannot drift.

## Domain Semantics

- Supported: **`KONTOOR`, `UNGER`, `ROLE PERSONAL`, `CLIENTES`** — exactly Role's four; no others.
- Input is case-insensitive and tolerates underscores/extra spaces (`role_personal` → `ROLE PERSONAL`); stored upper-case.
- `NULL`/blank = **unclassified**, a first-class state. Migration never guesses a domain.
- Anything else is **rejected** (API 422 / `ValueError`), never coerced to a nearest match.
- Not implemented via tags.

## Client Semantics

- `client_name` is optional free text (whitespace-normalised), **allowed only when domain is `CLIENTES`**; supplying it under any other domain is rejected.
- Not required for any domain, including `CLIENTES`.
- Moving an item away from `CLIENTES` clears its `client_name`. Setting `domain: null` clears both.

## Kind Semantics

- Supported: **`project`** (default) and **`tool`**. Anything else (including `task`) is rejected.
- Every existing adopted row is a genuine project, so `'project'` is accurate, not an assumption.
- Tools live in the same managed-work table (adoption, resume, notes, dashboard all keep working). Ranking treatment of `tool` items is **not changed** in this task (see Remaining Gaps).

## Status Semantics

Status remains **free text** for backwards compatibility (no value restriction added; no runtime data normalised). Recognised behaviours after this task:

| Status word | Behaviour |
|---|---|
| `active` (default), anything unrecognised | competes normally (unchanged) |
| `paused`, `on_hold`, `archived` | still competes, **−20 score penalty** (unchanged) |
| `blocked`, `at_risk` | still competes, **−15 penalty** (unchanged) |
| **`completed`** (new) | **excluded from every active recommendation**; not deleted; not archived; stays queryable/visible |

`completed ≠ archived`. Archived means parked and keeps its existing paused treatment. A legacy word such as `Completado` (used historically for ROLE MASTER's v1.0 milestone) is **not** treated as `completed` — no data was rewritten, and **ROLE MASTER's status is untouched (`active`)**.

## Migration Behaviour

- Uses the repository's existing mechanism: idempotent `ALTER TABLE … ADD COLUMN` in `workspace.db.ensure_schema` (same pattern as the Sprint 3/5 columns). It runs when the application next opens the workspace DB.
- **Non-destructive and idempotent:** verified on a *copy* of the real canonical workspace DB (scratchpad, never the original): 5 rows before → 5 after; every pre-existing column value identical; new columns read `domain=NULL, client_name=NULL, kind='project'`; running twice was a no-op; `PRAGMA integrity_check: ok`. A dedicated test also builds a legacy-shaped DB (including a `Completado` status and a note) and proves it survives unchanged.
- **The canonical DB itself has not yet been migrated** — it will be, automatically and additively, the first time the app runs against it. Tests use isolated DBs.

## Mission Control: Completed Exclusion

`completed` is computed once (`is_completed` on `ProjectContext`, true if either the adoption overlay or the PI project status says completed) and honoured at each recommendation source, so every consumer is covered:

| Where | Change |
|---|---|
| `executive_decision/service.py` | completed projects do not compete → not in `decision`, `ranked_projects` |
| `workspace/advisor.generate_recommendations` | completed items yield no recommendations (feeds OI, `/workspace/advisor`, `advisor_summary`) |
| `operational_intelligence/engine.py` | completed contexts/items removed before the new rules run; PI-advisor recs for completed projects dropped → Today's Focus, Needs Attention, Value Signal, Daily Session |
| `workspace/portfolio.suggested_project_to_continue` | completed is never "the project to continue" → Primary Focus / "What matters now" |

Unchanged: `total_projects_tracked`, the portfolio strip and the Projects/Workspace lists still show completed items (history remains available); `last_active_project` remains a factual last-activity lookup. Where I Left Off, What Matters Now, What's Next and Resume Work were verified by tests and are unchanged.

## API / Service Compatibility

Minimum plumbing only: `AdoptRequest`/`OverlayUpdate` accept the three fields (validated at the Pydantic boundary → 422; PATCH cross-field rule enforced in `db.update_overlay`, surfaced as 422), `WorkspaceItem` and `ProjectContext` serialise them. A PATCH with an explicit `null` for `domain`/`client_name` clears it. Clients that send none of the fields behave exactly as before. No UI, filters, or dashboard link added.

## Tests

`dashboard/tests/test_work_classification.py` — 32 tests: vocabulary/normalisation, unknown domain/kind rejected, `task` rejected, client_name rules and clearing, tool round-trip, DB and Pydantic validation, legacy-schema migration (additive, idempotent, values preserved), API backwards compatibility, ProjectContext fields, completed excluded from *ranked_projects / decision / Today's Focus / Needs Attention / Primary Focus* and from workspace advisor recs, completed remains visible (portfolio, workspace list), `archived ≠ completed` (still competes), paused/blocked behaviour preserved, completed tool excluded, Mission Control shape unchanged, Resume Work for classified and completed items. A mutation check (temporarily removing the Executive Decision filter) made the exclusion test fail, confirming the test is real.

Results: focused related suites 569 passed; full suite split as in Phase 2 — `tests/` 8, `builder/tests/` 26, `dashboard/tests/` 1,370 → **1,404 passed, 0 failed** (1,372 previously + 32 new).

## Runtime Safety

SHA256/size/mtime of all **15** runtime DB files (5 in `ROLE_KNOWLEDGE_OS/00_SYSTEM/`, `var/role_os/`, `var/role_os_alpha/`, `var/role_os_dashboard/`) recorded before and after implementation, the migration proof, and the full test runs: **identical**. `PRAGMA integrity_check` ok on all; `adopted_projects` = 5 rows. `var/role_os_alpha/`, `pi_ai_workspace`, Discovery roots and adoptions were not touched.

## Remaining Gaps

- The canonical DB gains its new columns only when the app first runs against it (by design).
- Nothing sets `domain`/`kind`/`completed` for real projects yet, and there is no UI to do so (P3.3; today via `PATCH /workspace/discovered/{id}`).
- `tool` items are not yet treated specially by ranking; whether tools should be excluded from "what to do now" is a P3.3 decision. (None exist yet.)
- Portfolio strip does not yet group active/completed/tools, and Mission Control does not yet expose `domain` per item — P3.3.
- Status stays free text; unrecognised legacy words (`Completado`) are not interpreted.

## Proposed Classification (review only — NOT persisted)

| Project | Current status | Proposed domain | Proposed kind | Confidence | Reason |
|---|---|---|---|---|---|
| ROLE OS | active | ROLE PERSONAL | project | High | Role's own product/repo |
| ROLE Commerce Factory | active | ROLE PERSONAL | project | High | Role's own product (registry: Software, private repo `rolevc-valdez`) |
| ROLE MASTER | active | ROLE PERSONAL | project | High | Role's own project; status stays `active` (its "Completado" was a v1.0 milestone) |
| role-ecosystem | active | ROLE PERSONAL | project | High | Role's strategy/docs repo |
| ROLE_KNOWLEDGE_OS | active | ROLE PERSONAL | project | Medium | Role's builder/knowledge system, but its knowledge cards reference Kontoor/Unger material — Role to confirm |

None of these is applied; Role approves classification separately. No new projects were adopted.
