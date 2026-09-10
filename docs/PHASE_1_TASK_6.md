# Role OS 2.0 — Phase 1 Task 6

## Objective

Resolve the untracked, root-level `project-dashboard.html` — a self-contained, independently-built "project map" page that shared no code, data, or route with `dashboard/app` — without losing useful information or assets, and without leaving it as a second, competing dashboard.

## Legacy Dashboard Assessment

`project-dashboard.html` (27,223 bytes, single self-contained file, Spanish UI "Mapa de proyectos"): a hand-curated catalog of Role's projects/tools/scripts, persisted to the browser's own `localStorage` (key `role-project-map-v1`), with a hardcoded 10-item `starter` array as default seed data. Confirmed (Task 3/audit): zero shared code, data, or route with `dashboard/app`; zero references from any launcher script (`Start-RoleOS.ps1`, `.bat` files) or active documentation (`README.md`, `INSTALLATION.md`, `QUICK_START.md`, `DEMO.md` — all checked, zero hits).

## Legacy Data Inventory

The hardcoded `starter` list, 10 items, each with: `id`, `category`, `name`, `kind`, `status`, `description` (rich text), `usage` (rich text), `path`, `url`. A special `ROLE_MASTER` card additionally exposes: a copy-prompt-and-open-ChatGPT action, a copy-`claude`-CLI-command action, and links to two local image assets (`assets/role-master/RM-000.png`, `assets/role-master/rolevaldez_official.png`, relative to the file's own original location at the repo root).

## Canonical Mapping

Compared against Role OS 2.0's canonical adopted projects (Task 3D: ROLE OS, ROLE_KNOWLEDGE_OS, ROLE Commerce Factory, ROLE MASTER, role-ecosystem):

| Legacy item | Legacy path | Canonical match | Classification |
|---|---|---|---|
| `role-master` (ROLE MASTER) | `...\ROLE MASTER` | ROLE MASTER (`f2f7af289a68576f`) | Exact match — description/usage MIGRATED |
| `commerce` (ROLE Commerce Factory) | `...\ROLE Commerce Factory` | ROLE Commerce Factory (`2c181c8974771e32`) | Exact match — description/usage MIGRATED |
| `ecosystem` (role-ecosystem) | `...\role-ecosystem` | role-ecosystem (`98f8bbca43bfbd88`) | Exact match — description/usage MIGRATED |
| `knowledge` (ROLE Knowledge OS) | `...\ROLE_KNOWLEDGE_OS` | ROLE_KNOWLEDGE_OS (`853dea81cc23fb17`) | Same folder, renamed label — description/usage MIGRATED |
| `role-os` (ROLE OS) | `...\ROLE_OS` | ROLE OS (`60ae784ee6c67df0`) | Exact match — description/usage MIGRATED |
| `role-content-factory` (Role Content Factory) | `Documents\role-content-factory` | **None** | LEGACY-ONLY — real project, not adopted, not auto-adopted |
| `role-dashboard` (ROLE DASHBOARD) | `...\ROLE DB` | **None** (self-referential, describes this very file) | OBSOLETE |
| `subir-libros-etsy` (Subir Libros a ETSY) | `Documents\rolevaldez.com\agregar_libro.py` | **None** | LEGACY-ONLY — real script, not adopted, not auto-adopted |
| `assets` (ROLE Assets) | `...\ROLE ASSETS` | **None** | ARCHIVE ONLY — a folder reference, not a project; real folder confirmed to exist |
| `others` (Otros · no proyectos) | `...\OTROS - no proyectos` | **None** | ARCHIVE ONLY — a catch-all bucket, already independently found by real Discovery scans (see Task 3C's `workspace_scan_cache` dump) |

**Legacy-only, not migrated, not auto-adopted (per this task's explicit instruction)**: `role-content-factory` and `subir-libros-etsy` are real, verified-to-exist projects/scripts outside the `1 - IA PROJECTS` Discovery root entirely (under `Documents\`). Discovery would not find them without `ROLE_OS_DISCOVERY_EXTRA_EXCLUSIONS`/root changes. Flagged for Role's awareness, not adopted.

**No canonical-only projects** — all 5 canonical adopted projects had a legacy match.

## Metadata Migrated

Exactly 5 notes added, one per matching canonical project, via the existing `POST /workspace/discovered/{item_id}/notes` API (the same code path the application itself uses — no manual database editing), each prefixed `[Migrated from legacy project-dashboard.html, archived 2026-09-10]` and containing that project's legacy description + usage text (HTML stripped, Spanish text preserved as written). Printed and reviewed before execution (see the conversation's own "Proposed Metadata Migration" table). Verified after: all 5 target projects still number exactly 5 in `adopted_projects` (no rows created or duplicated), each now has exactly 1 note, and `status`/`priority`/`tags` are untouched on every row.

**Conflict found, not overwritten**: ROLE MASTER's legacy `status` was `"Completado"` (Completed) while its canonical `status` is `"active"` — left as-is; only `notes` was appended.

## Metadata Not Migrated

- `role-dashboard`'s own description/usage — obsolete, describes the file being archived.
- `assets` / `others` — not real projects in the canonical sense; no canonical field to migrate into.
- `role-content-factory` / `subir-libros-etsy` — real, useful, but have no canonical project to attach to (not adopted); documented above instead, per "do not auto-adopt legacy-only projects."
- The ROLE MASTER card's ChatGPT-prompt-copy and Claude-CLI-command-copy *behaviors* — UI-only conveniences with no canonical data-model equivalent; not ported (would be new functionality, out of this task's scope of "resolve the legacy file," not "reimplement its features").

## LocalStorage Limitation

This repository's copy of `project-dashboard.html` can only prove what its own hardcoded `starter` array contains — it cannot prove or disprove what a real browser's `localStorage` (key `role-project-map-v1`) currently holds if Role ever added or edited cards through the page's own UI. No exported backup file (the page's own "Exportar" button produces `role-projects-backup.json`) was found anywhere in this repository. This limitation is stated explicitly, not glossed over, in `archive/legacy-dashboard/README.md`. Archival was **not blocked** on this uncertainty, per this task's explicit instruction — the file itself is fully preserved, so any future recovery from a browser profile remains possible against the archived copy.

## Role Master Assets

`assets/role-master/RM-000.png` (2,465,255 bytes) and `assets/role-master/rolevaldez_official.png` (1,790,121 bytes) — confirmed real PNG images, confirmed `project-dashboard.html` was their only consumer in this repository (no reference anywhere in `dashboard/app`), confirmed they are genuine Role Master brand assets rather than throwaway decoration. **Not deleted, not moved** — left at their original path (`assets/role-master/`, repo root), since no other current Role OS system consumes or requires relocating them, and moving them would break even the *documented* (not functional) relative-path relationship the archived HTML still describes.

## Archive Location

`archive/legacy-dashboard/project-dashboard.html` (no pre-existing archive convention was found in this repository, so the task's suggested default path was used) — byte-identical to the original (27,223 bytes, original Aug 14 mtime preserved by the file move), plus a new `archive/legacy-dashboard/README.md` explaining what it was, why it was retired, when, what replaced it, the localStorage limitation, and where the Role Master assets remain.

## Active Dashboard After Task 6

One operational dashboard: **Mission Control** (`GET /`, `GET /mission-control`). One preserved historical dashboard: the archived `project-dashboard.html`, no longer reachable from the repository root, no longer referenced by any launcher or active documentation.

## Files Changed

- `archive/legacy-dashboard/project-dashboard.html` — new (moved from repo root, byte-identical)
- `archive/legacy-dashboard/README.md` — new
- `docs/PHASE_1_TASK_6.md` — new
- `var/role_os_dashboard/role_os_workspace.db` — 5 notes added via the existing API (not a schema or code change; runtime data, not committed — see Files Changed's git scope below)

No application source code was modified in this task.

## Tests / Validation

No application code changed, so no new tests were written (per this task's own "if no application code changes, do not invent unnecessary tests" instruction). Ran the existing `workspace`/`mission_control` keyword-matched regression slice to confirm the note-migration calls and file move caused no regression: **273 passed, 0 failed**. Repository-level checks: `project-dashboard.html` confirmed absent from the repo root; `archive/legacy-dashboard/` confirmed present with both files; zero references to `project-dashboard.html` remain in any launcher script or active top-level documentation (`README.md`, `INSTALLATION.md`, `QUICK_START.md`, `DEMO.md`).

## Known Limitations

- The two legacy-only real projects (`role-content-factory`, `subir-libros-etsy`) remain undiscovered by normal Role OS Discovery (they live outside the default scan root) — flagged, not resolved; a future Role decision, not this task's job.
- The archived HTML's internal image references will not resolve if opened directly from its new archive location (documented in the archive README as an accepted trade-off of byte-for-byte preservation).
- Any browser-local `localStorage` edits beyond the hardcoded `starter` array remain unrecoverable from this repository (see LocalStorage Limitation above).

## Exact Next Task

Phase 1 — Task 7: Markdown Control Files
