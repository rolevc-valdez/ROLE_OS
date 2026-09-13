# Role OS 2.0 — Phase 2 Task 1: Test Isolation Hardening

## Objective

Ensure automated tests cannot accidentally write to or mutate canonical Role OS runtime data. This must close before Multi-Root Discovery (Task 2) begins, since that task will add more Discovery-triggering test coverage that would otherwise compound the existing leak.

## Investigation

Read `CURRENT_STATE.md`, `NEXT_ACTIONS.md`, and `docs/ROLE_OS_2_PHASE_2_PLAN.md` first, per the task brief. Then inspected `dashboard/tests/conftest.py` directly and searched the whole test tree for every `ROLE_OS_*` environment variable name, rather than assuming `conftest.py` alone was the full picture.

**Every dashboard-owned path field** (from `dashboard/app/config.py: Settings`): `db_path`, `projects_db_path`, `advisor_db_path`, `imports_db_path`, `extraction_db_path`, `session_db_path`, `workspace_db_path`, `assets_db_path`, `asset_thumbnail_cache_dir`, `ecosystem_db_path` — 10 fields, 10 environment variables.

**What `conftest.py` set before this task:** 7 of the 10, each via `os.environ.setdefault(...)` with a `tempfile.mkdtemp()`-backed path — `ROLE_OS_DB_PATH` (pointed at the real, read-only, committed sample fixture — intentional, not a gap), `ROLE_OS_PROJECTS_DB_PATH`, `ROLE_OS_ADVISOR_DB_PATH`, `ROLE_OS_IMPORTS_DB_PATH`, `ROLE_OS_EXTRACTION_DB_PATH`, `ROLE_OS_SESSION_DB_PATH`, `ROLE_OS_WORKSPACE_DB_PATH`.

**Root cause:** `ROLE_OS_ASSETS_DB_PATH`, `ROLE_OS_ASSET_THUMBNAIL_CACHE_DIR`, and `ROLE_OS_ECOSYSTEM_DB_PATH` had **no session-wide default**. A repository-wide search found that five individual test files (`test_assets_os.py`, `test_executive_decision.py`, `test_impact_analysis.py`, `test_project_ecosystem.py`, `test_session_intent.py`) already isolate these three variables themselves, ad-hoc, via `monkeypatch.setenv(...)` inside specific test functions — but **any other test anywhere in the ~1,347-test suite** that happened to exercise Assets OS or Ecosystem code without its own explicit override (most notably anything touching Mission Control's shared `request_scope()` filesystem walk, or `/workspace/rescan`) fell straight through to `config.py`'s real default: the actual `var/role_os_dashboard/role_os_assets.db`, `asset_thumbnails/`, and `role_os_ecosystem.db` — not a fixture. This exact leak was observed and disclosed repeatedly throughout Phase 1 (Tasks 1, 3B, 3D, 4, 5, 8B, and Final Validation all noted `role_os_assets.db` growing after a test run).

**`ROLE_OS_WORKSPACE_DIR` — checked, found irrelevant to this fix:** this variable is read only by `scripts/RoleOS.Common.ps1` (the PowerShell launcher); `dashboard/app/config.py` has no knowledge of it at all. It cannot affect Python test isolation and was correctly out of scope here.

## Isolation Strategy

Extended `dashboard/tests/conftest.py`'s existing, proven pattern — `os.environ.setdefault(NAME, str(Path(tempfile.mkdtemp(prefix=...)) / filename))` — to the three missing variables, using the exact same style and placement convention as the other seven. No new mechanism, no new pattern, no new persistence: the fix is the same one-line-per-variable idiom already used successfully for a decade of prior sprints' worth of domains.

Also added a **regression guard**, not just a fix: `test_all_ten_dashboard_db_env_vars_are_set_by_conftest` fails if any future new path field is added to `Settings` without a matching `conftest.py` default, and `test_real_test_session_never_resolves_into_the_real_var_role_os_directory` directly asserts — against the *real* session environment, not a synthetic clean-slate scenario — that every one of the ten fields resolves outside the actual `var/role_os/` and `var/role_os_dashboard/` directories. Together these two tests make this class of bug fail loudly the next time it's introduced, rather than silently reappearing.

## Canonical Runtime Paths Protected

`var/role_os_dashboard/role_os_assets.db`, `var/role_os_dashboard/asset_thumbnails/`, `var/role_os_dashboard/role_os_ecosystem.db` — the three that were previously exposed. The other seven were already correctly isolated and remain unchanged.

## Implementation

`dashboard/tests/conftest.py`: two new blocks, following the existing convention exactly —
- `ROLE_OS_ASSETS_DB_PATH` and `ROLE_OS_ASSET_THUMBNAIL_CACHE_DIR` share one fresh `tempfile.mkdtemp()` directory (mirroring how they're related, both under `assets_db_path`'s conceptual family, in `config.py` itself).
- `ROLE_OS_ECOSYSTEM_DB_PATH` gets its own fresh `tempfile.mkdtemp()` directory.

No canonical production default in `dashboard/app/config.py` was touched. No existing test file's own `monkeypatch.setenv()` calls were changed — per-test overrides still correctly take precedence over the new session-wide defaults for the duration of that specific test, exactly as `monkeypatch` is designed to work.

## Validation

**Before any test ran**, recorded SHA256 checksums and mtimes of every canonical file in the affected family:
- `role_os_workspace.db`: `3b2657b7...deedd68`
- `role_os_session.db`: `c03adb7d...b697a17`
- `role_os_ecosystem.db`: `05cd65c1...8927a85`
- `role_os_assets.db`: `48168f57...898aa8f`
- `asset_thumbnails/`: 9 files

**Focused isolation tests** (`dashboard/tests/test_config.py`, 19 tests including the 2 new regression guards): **19 passed**. Checksums re-verified identical immediately after — including `role_os_assets.db`, the file that historically grew on every run.

**Targeted regression slice** — specifically the 8 test files most implicated in the historical leak (`test_assets_os.py`, `test_executive_decision.py`, `test_impact_analysis.py`, `test_project_ecosystem.py`, `test_session_intent.py`, `test_mission_control_api.py`, `test_mission_control_freshness_ui.py`, `test_workspace_service.py`): **202 passed**. Checksums re-verified identical again — including `asset_thumbnails/`'s file count (unchanged at 9) and `var/role_os/`'s contents (mtimes unchanged).

**Full `dashboard/tests` suite** (the broadest possible regression slice, run as its own process to avoid this environment's earlier memory-limit issue with the combined `tests`+`dashboard/tests`+`builder/tests` invocation): **1,315 passed, 0 failed, 0 skipped, 0 errors** in 44m13s (1,313 pre-existing + the 2 new regression-guard tests). Checksums verified identical a third and final time immediately after this run — `role_os_assets.db`, the exact file that historically grew on every single Phase 1 test run, is now byte-for-byte unchanged across the entire suite. `asset_thumbnails/` file count unchanged (9). `var/role_os/`'s file mtimes unchanged from before this task began.

No live production-data smoke test was performed to validate this fix, per the task brief's explicit instruction — isolation is proven by database checksums remaining unchanged across real test runs, not by a separate manual server check.

## Files Changed

- `dashboard/tests/conftest.py` — 2 new blocks (`ROLE_OS_ASSETS_DB_PATH`/`ROLE_OS_ASSET_THUMBNAIL_CACHE_DIR`, `ROLE_OS_ECOSYSTEM_DB_PATH`)
- `dashboard/tests/test_config.py` — 2 new regression-guard tests, 1 new import (`os`)
- `docs/PHASE_2_TASK_1_TEST_ISOLATION.md` — this file

No production code (`dashboard/app/`) was changed. No canonical production default was changed.

## Known Limitations

- This fix isolates *dashboard-owned SQLite/cache path* fields specifically. It does not audit every conceivable filesystem side effect a test could have (e.g. a test that calls Discovery against a real, non-tmp_path root would still scan real folders — but every test observed in this codebase already correctly passes an explicit `tmp_path`-rooted `root` to Discovery/Workspace endpoints, so this was not found to be a live issue during this task).
- The five test files that already had their own ad-hoc `monkeypatch.setenv()` calls for these three variables were left as-is (their per-test overrides are now simply redundant-but-harmless with the new session-wide default) rather than removed, to keep this change minimal and avoid touching test files beyond what was strictly necessary to close the gap.
