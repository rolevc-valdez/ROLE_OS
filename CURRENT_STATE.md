# Role OS 2.0 — Current State

*This file describes NOW. It is overwritten at every completed major task, not appended to. For how something happened, read `docs/PHASE_1_TASK_*.md`, `docs/product/DECISIONS.md`, or `git log` — never this file.*

## Status

- **Phase:** Role OS 2.0, Phase 1 (Core Consolidation)
- **Current task:** Phase 1 — Final Validation / Completion Review (not started)
- **Last completed task:** Phase 1 — Task 9: Discovery Report Artifacts
- **Last completed commit:** this commit — run `git log -1` to get its exact hash (always verify against git, per the Recovery procedure below, rather than trusting a hardcoded value here)
- **Overall state:** Stable. Mission Control is the one operational dashboard, backed by real, migrated, verified canonical data. No known regressions. Every task explicitly scoped for Phase 1 (Tasks 1–9) is now complete.

## What Is Working

- Canonical runtime paths are anchored to the repository root regardless of launch directory (Task 3B), not the process's working directory.
- Real, verified project state — 5 adopted projects and the Daily Session registry — lives at the canonical runtime location (Task 3D).
- Mission Control (`GET /`, `GET /mission-control`) is the single landing experience (Task 4), answering all three core questions in order on one screen: Where I Left Off → What Matters Now → What's Next, with a prominent Continue Working / Resume Work action.
- Resume Work uses the existing, unmodified backend (`workspace/resume.py`, `workspace/execution_target.py`) — no parallel implementation.
- Staleness and fallback data can no longer silently masquerade as current (Task 5): a stale-data note on the Executive Decision card, and a Live/Fallback badge on ecosystem decisions.
- The legacy `project-dashboard.html` is archived, not deleted; its useful, non-conflicting metadata was migrated into the canonical workspace notes; Role Master brand assets are preserved and now tracked in git (Task 6).
- Runtime/user data (SQLite databases under `var/`) is never committed to git.
- Navigation is now grouped into 5 clusters — Mission Control, Projects, Knowledge, Session, Settings (Task 8B) — with Dashboard v2 demoted to a "See full metrics →" link from Mission Control. All 32 routers, every route path, and every deep link are unchanged; nothing was removed (see `docs/PHASE_1_TASK_8B.md`).
- `var/discovery_reports/`'s ambiguity is resolved (Task 9): its one report, found to contain unique information, is preserved at `archive/discovery-reports/documents-2026-07-31/`; the report-generation tool itself (`discovery/reporters.py`) remains a working, tested, on-demand manual export capability — see `docs/PHASE_1_TASK_9.md`.

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

Only items genuinely unresolved as of the last completed task:

1. **`var/role_os_alpha/` disposition** — contains real-sounding, non-overlapping project data (Kontoor, Unger, Charcos, SUPER FACIL, RoleValdez) of uncertain provenance. Not merged, not discarded. Needs Role's judgment call (see `docs/RUNTIME_DATA_MAP.md`, "role_os_alpha Assessment").
2. **`dashboard/tests/conftest.py`'s isolation gap** — `ROLE_OS_ASSETS_DB_PATH`/`ROLE_OS_ECOSYSTEM_DB_PATH` aren't sandboxed per test run, so running the suite still writes cache rows into the real `var/role_os_dashboard/role_os_assets.db`. Harmless (cache-only) but not yet fixed.
3. **`dashboard/var/role_os_dashboard/` (the pre-migration legacy copy)** — still exists, unused, containing the original 14-row `adopted_projects` (5 real + 9 stale manual-debug rows). Not deleted. Safe to clean up once Role confirms nothing there is still needed.
4. **Real projects outside the Discovery root** — `role-content-factory` and `rolevaldez.com`/`subir-libros-etsy` (Task 6), plus `SUPER-FACIL`, `AGUA-AZUL-APP`/`agua-azul-app`, `charcos-site`, `desierto-creativo-site` (Task 9, from the archived `Documents` audit — `archive/discovery-reports/documents-2026-07-31/`) — none discoverable by Role OS's default scan root, none adopted. Role's awareness only.
5. **ROLE MASTER status mismatch** — legacy catalog said "Completado"; canonical `adopted_projects.status` says `"active"`. Left as-is (Task 6); not overwritten, not resolved either way.
6. **`pi_ai_workspace` (legacy v1.3 fields) vs. `pi_ai_sessions` (v1.4)** — Task 8 flagged this router pair as REVIEW: whether any real project still has data only in the superseded v1.3 fields was not checked (would require opening a database beyond this analysis-only task's scope).

## Recovery

1. Read this file (`CURRENT_STATE.md`).
2. Read `NEXT_ACTIONS.md`.
3. Run `git status` and `git log -5` — confirm the repository actually matches what this file claims (if it doesn't, trust the repository, not this file, and treat the mismatch itself as the first thing to investigate).
4. Continue only the task named in `NEXT_ACTIONS.md`'s "Now" section.

**Do NOT repeat any task listed above as completed.** Their full implementation detail is in `docs/PHASE_1_TASK_*.md`, not here — read the specific task doc if you need to understand *how* something was done, not this file.
