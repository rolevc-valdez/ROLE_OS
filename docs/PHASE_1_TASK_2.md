# Role OS 2.0 — Phase 1 Task 2

## Problem

`dashboard/app/config.py` defaulted five dashboard-owned SQLite databases into the bundled `samples/role_os_sample/00_SYSTEM/` fixture tree whenever their environment variable wasn't set: `ROLE_OS_DB_PATH` (Knowledge), `ROLE_OS_PROJECTS_DB_PATH` (Project Intelligence — the table behind Resume Work, Project Memory, and Mission Control), `ROLE_OS_ADVISOR_DB_PATH`, `ROLE_OS_IMPORTS_DB_PATH`, and `ROLE_OS_EXTRACTION_DB_PATH`. Of these, Projects/Advisor/Imports/Extraction are all dashboard-written stores — normal use (adopting a project, running Advisor, importing a ChatGPT export, extracting knowledge) would silently write real, growing data into what is supposed to be a static demo fixture, with zero indication to the user. This was flagged in `audits/ROLE_OS_1X_AUDIT.md` and named as the single highest-leverage fix in `docs/ROLE_OS_2_ARCHITECTURE_PROPOSAL.md`'s Migration Strategy (step 1) and Components That Need Simplification.

## Previous Behavior

| Field | Previous default (relative to CWD) |
|---|---|
| `db_path` (Knowledge) | `samples/role_os_sample/00_SYSTEM/role_os.db` |
| `projects_db_path` | `samples/role_os_sample/00_SYSTEM/role_os_projects.db` |
| `advisor_db_path` | `samples/role_os_sample/00_SYSTEM/role_os_advisor.db` |
| `imports_db_path` | `samples/role_os_sample/00_SYSTEM/role_os_imports.db` |
| `extraction_db_path` | `samples/role_os_sample/00_SYSTEM/role_os_extraction.db` |

All five paths are resolved via `Path(...).resolve()` against the process's current working directory (unchanged behavior) — see `docs/PHASE_1_BASELINE.md`'s Current Configuration table for the CWD-anchoring caveat this interacts with.

`workspace_db_path`, `session_db_path`, `assets_db_path`, `asset_thumbnail_cache_dir`, and `ecosystem_db_path` were already correctly defaulted under `var/role_os_dashboard/` and were **not part of this defect** — left untouched.

## New Runtime Default

Canonical runtime data root for normal (no-env-var) startup: **`var/role_os/`**.

| Field | New default (relative to CWD) |
|---|---|
| `db_path` (Knowledge) | `var/role_os/role_os.db` |
| `projects_db_path` | `var/role_os/role_os_projects.db` |
| `advisor_db_path` | `var/role_os/role_os_advisor.db` |
| `imports_db_path` | `var/role_os/role_os_imports.db` |
| `extraction_db_path` | `var/role_os/role_os_extraction.db` |

This is a pure default-value change — same `Path(os.environ.get(VAR, default)).resolve()` pattern used everywhere else in `config.py`, no new configuration mechanism.

`var/role_os_dashboard/` (workspace/session/assets/ecosystem) and `var/role_os_alpha/` were deliberately **not** touched, renamed, or consolidated into `var/role_os/` in this task — doing so would mean redirecting config away from files that already hold real data, which is a migration decision explicitly reserved for **Phase 1 — Task 3: Runtime Data Directory**.

## Environment Variable Precedence

Unchanged. Every field still resolves as `os.environ.get(VAR_NAME, <default>)` — an explicit `ROLE_OS_*_DB_PATH` environment variable always wins, exactly as before. This includes the case of a user or the launcher script explicitly pointing one of these variables back at `samples/role_os_sample/00_SYSTEM/` (e.g. for a deliberate demo run) — that continues to work unchanged.

## Sample / Fixture Behavior

- `samples/role_os_sample/00_SYSTEM/` was not modified, moved, or deleted. It remains fully available, but is now reached only when explicitly selected via an environment variable — never as a silent default.
- `dashboard/tests/conftest.py` already explicitly sets `ROLE_OS_DB_PATH` to the sample Knowledge DB via `os.environ.setdefault(...)` (module-level, before any test runs) and already creates fresh `tempfile.mkdtemp()`-based paths for `ROLE_OS_PROJECTS_DB_PATH`/`ROLE_OS_ADVISOR_DB_PATH`/`ROLE_OS_IMPORTS_DB_PATH`/`ROLE_OS_EXTRACTION_DB_PATH`/`ROLE_OS_SESSION_DB_PATH`/`ROLE_OS_WORKSPACE_DB_PATH` — i.e. the test suite was **already** explicitly configuring every one of these paths and never depended on `config.py`'s bare default. No test fixture needed to change.
- `scripts/run_alpha.bat`/`.sh` and `scripts/seed_alpha_demo.py` explicitly set their own `ROLE_OS_DB_PATH`/`ROLE_OS_PROJECTS_DB_PATH`/`ROLE_OS_ADVISOR_DB_PATH` env vars pointing at `samples/` and `var/role_os_alpha/` respectively — unaffected by this change, already explicit.
- `scripts/RoleOS.Common.ps1`'s `Resolve-RoleOSDatabaseEnv` independently defaults the official `.bat` launcher to the bundled sample workspace (logging `"Database source: bundled sample workspace (default)"`) unless `ROLE_OS_WORKSPACE_DIR` is set — this is a distinct, already-visible (logged), separately-documented launcher UX decision, not silent, and was **not modified** in this task (see Known Limitations).

## Files Changed

- `dashboard/app/config.py` — five default path string changes plus an explanatory comment; no other logic touched.
- `dashboard/tests/test_config.py` — new file, 10 focused tests (see below).
- `docs/PHASE_1_BASELINE.md` — one clearly marked "Post-Baseline Note" section appended; no existing content rewritten.
- `docs/PHASE_1_TASK_2.md` — this file.

## Tests Added or Updated

New file `dashboard/tests/test_config.py` (10 tests, all passing):

1. `test_normal_runtime_default_does_not_point_into_samples`
2. `test_knowledge_db_normal_default_is_under_var_role_os`
3. `test_projects_db_normal_default_is_under_var_role_os`
4. `test_advisor_imports_extraction_db_defaults_are_under_var_role_os`
5. `test_explicit_db_path_override_still_works`
6. `test_explicit_projects_db_path_override_still_works`
7. `test_tests_and_demos_can_explicitly_select_the_sample_knowledge_db`
8. `test_no_silent_fallback_to_samples_when_normal_runtime_db_path_is_unset`
9. `test_projects_db_still_auto_creates_at_the_new_default_location` — proves `app/projects/db.py: get_connection`'s existing `mkdir(parents=True, exist_ok=True)` + `CREATE TABLE IF NOT EXISTS` behavior is unaffected by the new default
10. `test_missing_knowledge_db_at_new_default_fails_clearly_not_silently` — proves `app/db.py`'s existing `DatabaseUnavailableError`/`database_exists()` behavior for the read-only Knowledge DB is unaffected

No existing test file needed updating — `conftest.py` already explicitly set every one of these five environment variables for the whole suite (see Sample / Fixture Behavior above), so no test was "accidentally" relying on `config.py`'s bare default.

## Data Safety

Verified directly (see completion report below for full detail): no database was copied, migrated, or deleted; `var/role_os_alpha/` file mtimes unchanged; no `var/role_os/` directory was created by this task (the two new-default-location tests use `tmp_path`, never the real path); `samples/` untouched; no existing SQLite file's contents were modified by this task's own changes (a real write to `var/role_os_dashboard/role_os_assets.db` happened during Phase 1 Task 1's startup smoke test, already disclosed in `docs/PHASE_1_BASELINE.md`, and is unrelated to Task 2).

## Known Limitations

- `scripts/RoleOS.Common.ps1`'s `Resolve-RoleOSDatabaseEnv` still independently defaults the official `Start-RoleOS.ps1`/`Start ROLE OS.bat` launcher to `samples/role_os_sample/00_SYSTEM/` for all five databases (logged, not silent, and already has its own `ROLE_OS_WORKSPACE_DIR` opt-out) — this task changed `config.py`'s bare default only, which matters for direct `uvicorn app.main:app` startup (e.g. this task's own Phase 1 Task 1 smoke test) or any other launch path that doesn't go through the PowerShell launcher. Reconciling the launcher's own default with `config.py`'s new default was judged out of scope for a configuration-correctness-only task (it touches the launcher's documented, tested UX behavior, not just a config default) and is flagged here for Role's review rather than changed unilaterally.
- No `var/role_os/` directory exists yet anywhere on disk — first real startup with no env override will create it (via the existing auto-create behavior for Projects/Advisor/Imports/Extraction DBs) or report the Knowledge DB as missing/disconnected (existing, unchanged behavior). This is expected and intentional; populating it with real or migrated data is Task 3's job.
- The affected-area regression slice (557 tests across config/projects/workspace/resume/session/project-memory/project-context/settings/mission-control/executive-decision/health) was run and is fully green; the full 1,304-test baseline suite was **not** re-run in this task (see Testing below) and remains required at a later Phase 1 validation checkpoint.

## Exact Next Task

Phase 1 — Task 3: Runtime Data Directory
