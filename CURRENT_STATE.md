# Role OS 2.0 — Current State

*This file describes NOW. It is overwritten at every completed major task, not appended to. For how something happened, read `docs/PHASE_1_TASK_*.md`, `docs/PHASE_1_COMPLETION.md`, `docs/product/DECISIONS.md`, or `git log` — never this file.*

## Status

- **Phase:** Role OS 2.0, **Phase 1 — COMPLETE** (see `docs/PHASE_1_COMPLETION.md` for the full acceptance record)
- **Current task:** none — Phase 1's task queue is empty; Phase 2 has not been scoped yet
- **Last completed task:** Phase 1 — Final Validation / Completion Review
- **Last completed commit:** this commit — run `git log -1` to get its exact hash (always verify against git, per the Recovery procedure below, rather than trusting a hardcoded value here)
- **Overall state:** Stable and verified live, not just task-by-task. Mission Control answers all three core questions against real canonical data; Resume Work, staleness/fallback honesty, navigation, legacy-dashboard retirement, and discovery-report resolution were all re-verified against the running system, not assumed from individually-completed tasks.

## What Is Working

- Canonical runtime paths (`var/role_os/`, `var/role_os_dashboard/`) are anchored to the repository root regardless of launch directory — re-verified via 17 passing CWD-independence tests and a live start from `dashboard/` (the historically CWD-sensitive launch directory).
- Real, verified project state — 5 adopted projects, 7 Daily Session registry rows — confirmed present with `PRAGMA integrity_check: ok` on both canonical databases.
- Mission Control (`GET /`, `GET /mission-control`) answers all three core questions with real data — confirmed live during Final Validation: Where I Left Off (ROLE OS), What Matters Now (ROLE Commerce Factory), What's Next (3 real Today's Focus items).
- Resume Work uses the existing, unmodified backend — no parallel implementation exists anywhere.
- Staleness and fallback honesty is genuinely active right now, not just tested: real time passing pushed `data_freshness.is_stale` to `true` during Final Validation itself, and the system correctly discounted Executive Decision's confidence (0.85 → 0.72) and displayed the stale/fallback UI elements.
- The legacy `project-dashboard.html` remains archived (byte-identical, re-verified); Role Master assets remain tracked and unmodified.
- Navigation remains grouped into 5 clusters; all 32 routers and every deep link remain reachable — re-verified live.
- `var/discovery_reports/` remains resolved — archived, no ambiguous active persistence location.
- The full test suite (`tests`, `dashboard/tests`, `builder/tests`) passes completely: **1,347 collected, 1,347 passed, 0 failed, 0 skipped, 0 errors**.
- Runtime/user data (SQLite databases under `var/`) is never committed to git.

## Current Runtime Model

Two canonical runtime roots, both resolved from the repository root regardless of launch directory (`dashboard/app/config.py: Settings.repo_root`, derived from `__file__`, never CWD):

- **`var/role_os/`** — Knowledge/Project Intelligence/Advisor/Imports/Extraction family. Currently empty by default on this repository; the real, live data for this family lives **externally**, at `ROLE_KNOWLEDGE_OS\00_SYSTEM\`, selected via the persistent `ROLE_OS_WORKSPACE_DIR` environment variable — this is correct, intentional, and must not be copied into the repo.
- **`var/role_os_dashboard/`** — Workspace/Session/Assets/Ecosystem family. Holds the real, migrated canonical state: 5 adopted projects, 7 Daily Session registry entries.

Full inventory, provenance evidence, and the reasoning behind every decision above: **`docs/RUNTIME_DATA_MAP.md`**. Do not re-derive this from scratch — read that file first.

## Canonical Projects

The 5 real adopted projects, currently and only these:

- ROLE OS
- ROLE_KNOWLEDGE_OS
- ROLE Commerce Factory
- ROLE MASTER
- role-ecosystem

This list comes from `var/role_os_dashboard/role_os_workspace.db: adopted_projects`, not from `samples/`, not from `var/role_os_alpha/`. If a future session sees a different count, something changed — check `docs/RUNTIME_DATA_MAP.md` and `git log` before trusting either source blindly.

## Open Issues / Decisions

None of these block Phase 1's completion — every one is either explicitly Role's decision to make, or accepted, non-destructive technical debt (see `docs/PHASE_1_COMPLETION.md`'s Remaining Issues table for classification and risk):

1. **`var/role_os_alpha/` disposition** — contains real-sounding, non-overlapping project data (Kontoor, Unger, Charcos, SUPER FACIL, RoleValdez) of uncertain provenance. Not merged, not discarded. Needs Role's judgment call (see `docs/RUNTIME_DATA_MAP.md`, "role_os_alpha Assessment").
2. **`dashboard/tests/conftest.py`'s isolation gap** — `ROLE_OS_ASSETS_DB_PATH`/`ROLE_OS_ECOSYSTEM_DB_PATH` aren't sandboxed per test run, so running the suite still writes cache rows into the real `var/role_os_dashboard/role_os_assets.db`. Harmless (cache-only) but not yet fixed. Good low-risk Phase 2 entry point.
3. **`dashboard/var/role_os_dashboard/` (the pre-migration legacy copy)** — still exists, unused, containing the original 14-row `adopted_projects` (5 real + 9 stale manual-debug rows). Not deleted. Safe to clean up once Role confirms nothing there is still needed.
4. **Real projects outside the Discovery root** — `role-content-factory`, `rolevaldez.com`/`subir-libros-etsy` (Task 6), plus `SUPER-FACIL`, `AGUA-AZUL-APP`/`agua-azul-app`, `charcos-site`, `desierto-creativo-site` (Task 9, from the archived `Documents` audit). None discoverable by Role OS's default scan root, none adopted. Role's awareness only.
5. **ROLE MASTER status mismatch** — legacy catalog said "Completado"; canonical `adopted_projects.status` says `"active"`. Cosmetic, unresolved.
6. **`pi_ai_workspace` (legacy v1.3 fields) vs. `pi_ai_sessions` (v1.4)** — whether any real project still has data only in the superseded v1.3 fields was not checked.
7. **Stale top-level `README.md`/`ARCHITECTURE.md`/`app_version`** — never rewritten during Phase 1 (Phase 0's own documentation-drift finding, partially mitigated by this file existing and being kept current, but the original files themselves remain stale). Good Phase 2 entry point.

## Recovery

1. Read this file (`CURRENT_STATE.md`).
2. Read `NEXT_ACTIONS.md`.
3. Run `git status` and `git log -5` — confirm the repository actually matches what this file claims (if it doesn't, trust the repository, not this file, and treat the mismatch itself as the first thing to investigate).
4. Continue only the task named in `NEXT_ACTIONS.md`'s "Now" section.

**Do NOT repeat any task listed above as completed, and do NOT begin Phase 2 work without first reading `docs/PHASE_1_COMPLETION.md`.** Their full implementation detail is in `docs/PHASE_1_TASK_*.md`, not here — read the specific task doc if you need to understand *how* something was done, not this file.
