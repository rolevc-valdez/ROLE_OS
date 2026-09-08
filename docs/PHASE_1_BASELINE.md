# Role OS 2.0 — Phase 1 Baseline

## Baseline Date

2026-09-08

## Phase 1 Starting Commit

`e5d563e96fe8c25080590a5093e918a14210110e` (`main`, 2 commits ahead of `origin/main`)

## Git State

- Current branch: `main`
- HEAD: `e5d563e` — "feat: add operational manifest discovery support" (2026-09-08 08:48:06 -0700)
- Working tree: no modified or staged files; five intentionally preserved untracked items only (see below)
- Ahead of `origin/main` by 2 commits: `4acd3a3` (hotfix), `e5d563e` (operational manifest)

## Recent Relevant Commits

```
e5d563e (HEAD -> main) feat: add operational manifest discovery support
4acd3a3 fix: stabilize execution target and resume work detection
28736ec (origin/main, origin/HEAD) feat(dashboard): wire Dashboard 2.0, Explorer 2.0, Mission Control, Assets API, and register every domain router
0f35948 feat(executive-decision): add Executive Decision Engine
b7d4419 feat(impact-analysis): add Impact Analysis Engine
5399faa feat(project-ecosystem): add Project Ecosystem Engine
71e8aa0 feat(operational-intelligence): add Operational Intelligence Engine
b416fe4 feat(project-context): add ProjectContext consolidation
dcc8fc5 feat(sessions): add AI Sessions, AI Workspace, and Reconciliation API routers
ca16c78 feat(workspace): add Resume Work, canonical identity wiring, and Workspace service
```

## Registered Worktrees

```
C:/Users/rolev/My Drive (rolevc@gmail.com)/1 - IA PROJECTS/ROLE_OS   e5d563e [main]
C:/tmp/role_os_baseline_validation                                   6a1096a (detached HEAD)
```

The second entry is a pre-existing, unrelated worktree (files dated 2026-08-10, clean working tree, no uncommitted changes) — predates Phase 0 and has no connection to Role OS 2.0 work. Documented, not removed. A prior commit in this repo emitted a cosmetic `error: failed to delete '.git/worktrees/role_os_commit1_check': Permission denied` warning while Git attempted to auto-prune a separate stale worktree admin folder; the commit itself completed successfully and this warning has no effect on tracked content. No worktree cleanup was performed as part of Task 1.

## Intentional Untracked Files

- `audits/ROLE_OS_1X_AUDIT.md` — Phase 0 output, preserved
- `docs/ROLE_OS_2_ARCHITECTURE_PROPOSAL.md` — Phase 0.5 output, preserved
- `docs/ROLE_OS_2_DATA_MODEL_PROPOSAL.md` — Phase 0.5 output, preserved
- `project-dashboard.html` — legacy standalone prototype dashboard; recommended (per the architecture proposal) as archivable once its unique manually-curated content is copied into `adopted_projects`/`projects` notes; not touched in Task 1
- `assets/role-master/` — `RM-000.png`, `rolevaldez_official.png`; identified by the architecture proposal as `project-dashboard.html`'s own asset folder (referenced by its `roleMasterCard()` function), not orphaned and not part of Assets OS (`dashboard/app/assets/`); not touched in Task 1

No other unexpected modified or untracked files were found. `git status --porcelain` shows exactly these five items as `??` and nothing else.

## Current Runtime Data Locations

- `var/role_os_dashboard/` — real runtime data: `role_os_workspace.db`, `role_os_assets.db`, `role_os_ecosystem.db`, `asset_thumbnails/` (4 cached PNGs). `role_os_session.db` (configured default) does not yet exist on disk — created lazily on first use of Daily Session.
- `var/role_os_alpha/` — a second, parallel demo/alpha dataset (`role_os_advisor.db`, `role_os_projects.db`), seeded by `scripts/seed_alpha_demo.py`; purpose relative to `samples/` is undocumented (flagged by both the audit and the architecture proposal as needing a Role decision, not resolved in this task).
- `var/discovery_reports/documents/` — generated report artifacts (`documents_audit.json`, `.md`) with no current router consumer; candidate for removal per the architecture proposal, not touched here.
- `samples/role_os_sample/00_SYSTEM/` — fixture/demo data: `role_os.db`, `role_os_projects.db`, `MASTER_INDEX.md`. `role_os_advisor.db`, `role_os_imports.db`, `role_os_extraction.db` (all configured defaults under this same path) do not yet exist on disk — created lazily on first use.
- `samples/chatgpt_export_example/` — import-pipeline test fixture (not inspected further; out of scope for Task 1).

## SQLite Database Inventory

| Path | Size | Last Modified | Apparent Purpose | Kind |
|---|---|---|---|---|
| `samples/role_os_sample/00_SYSTEM/role_os.db` | 20,480 B | 2026-07-23 00:50:55 | Builder-generated Knowledge DB (`knowledge_cards`) | Fixture |
| `samples/role_os_sample/00_SYSTEM/role_os_projects.db` | 143,360 B | 2026-08-03 07:46:41 | Fixture Project Intelligence DB | Fixture |
| `var/role_os_alpha/role_os_advisor.db` | 40,960 B | 2026-07-23 00:51:26 | Alpha/demo Advisor DB | Demo (relationship to `samples/` undocumented) |
| `var/role_os_alpha/role_os_projects.db` | 98,304 B | 2026-07-23 00:51:25 | Alpha/demo Project Intelligence DB | Demo (relationship to `samples/` undocumented) |
| `var/role_os_dashboard/role_os_workspace.db` | 24,576 B | 2026-08-03 07:46:41 | Adopted-projects overlay + scan cache | Runtime (real user data) |
| `var/role_os_dashboard/role_os_ecosystem.db` | 12,288 B | 2026-08-05 06:37:27 | Relationship-override overlay | Runtime (real user data) |
| `var/role_os_dashboard/role_os_assets.db` | 143,360 B → 163,840 B* | 2026-08-11 08:46:16 → 2026-09-08 09:25:01* | Asset cache + user overrides | Runtime (cache regenerated during this task, see note below) |

\* **Note on this task's own side effect:** the Step 5 startup smoke test (below) started uvicorn with no environment overrides, so it used `config.py`'s real defaults — meaning it pointed at the actual `var/role_os_dashboard/` runtime databases and the actual `discovery_root` (this repo's real parent directory). Requesting `GET /` triggered a real filesystem asset scan, which **wrote new rows into `role_os_assets.db`'s `asset_cache` table** (size grew by 20,480 B; mtime updated to today). This table is explicitly documented in `config.py` as content-hash/mtime-keyed and safe to regenerate — no `asset_overrides` (user decisions) were touched, and `role_os_workspace.db`/`role_os_ecosystem.db` mtimes are unchanged, confirming no adoption or override data was affected. This is flagged transparently rather than silently absorbed into "no data changed."

No `.db-wal`, `.db-shm`, or `.db-journal` files exist anywhere under `var/` or `samples/` — no evidence of an interrupted write, before or after the smoke test.

`role_os_session.db`, `role_os_advisor.db` (dashboard-owned), `role_os_imports.db`, `role_os_extraction.db` do not exist yet at their configured default paths — untested/unused code paths as far as file creation goes.

## Current Configuration

From `dashboard/app/config.py` (unchanged, verified against HEAD):

| Setting | Env var | Default (relative to CWD) | Currently resolves under |
|---|---|---|---|
| Knowledge DB | `ROLE_OS_DB_PATH` | `samples/role_os_sample/00_SYSTEM/role_os.db` | `samples/` (fixture) |
| Project Intelligence DB | `ROLE_OS_PROJECTS_DB_PATH` | `samples/role_os_sample/00_SYSTEM/role_os_projects.db` | `samples/` (fixture) — **this is the known problem, see below** |
| Advisor DB | `ROLE_OS_ADVISOR_DB_PATH` | `samples/role_os_sample/00_SYSTEM/role_os_advisor.db` | `samples/` (fixture; file not yet created) |
| Imports DB | `ROLE_OS_IMPORTS_DB_PATH` | `samples/role_os_sample/00_SYSTEM/role_os_imports.db` | `samples/` (fixture; file not yet created) |
| Extraction DB | `ROLE_OS_EXTRACTION_DB_PATH` | `samples/role_os_sample/00_SYSTEM/role_os_extraction.db` | `samples/` (fixture; file not yet created) |
| Session DB | `ROLE_OS_SESSION_DB_PATH` | `var/role_os_dashboard/role_os_session.db` | `var/` (correct; file not yet created) |
| Workspace DB | `ROLE_OS_WORKSPACE_DB_PATH` | `var/role_os_dashboard/role_os_workspace.db` | `var/` (correct) |
| Assets DB | `ROLE_OS_ASSETS_DB_PATH` | `var/role_os_dashboard/role_os_assets.db` | `var/` (correct) |
| Ecosystem DB | `ROLE_OS_ECOSYSTEM_DB_PATH` | `var/role_os_dashboard/role_os_ecosystem.db` | `var/` (correct) |
| Discovery root | `ROLE_OS_DISCOVERY_ROOT` | this repo's parent directory | the real `1 - IA PROJECTS` folder |
| Discovery extra exclusions | `ROLE_OS_DISCOVERY_EXTRA_EXCLUSIONS` | empty | — |
| Obsidian daily notes dir | `ROLE_OS_OBSIDIAN_DAILY_NOTES_DIR` | empty | not configured |
| Ecosystem decision log path | `ROLE_OS_ECOSYSTEM_DECISION_LOG_PATH` | empty | not configured — `decisions_adapter.py` falls back to a hardcoded snapshot dated 2026-07-29/30 |
| Asset thumbnail cache dir | `ROLE_OS_ASSET_THUMBNAIL_CACHE_DIR` | `var/role_os_dashboard/asset_thumbnails` | `var/` (correct, safe-to-delete cache) |

All database paths are resolved via `Path(...).resolve()` against the **process's current working directory** — i.e. wherever `uvicorn` is launched from, not the repo root. `scripts/Start-RoleOS.ps1` compensates for this by explicitly re-anchoring all five `ROLE_OS_*_DB_PATH` env vars to the repository root before launching (see its own inline comments); this task's manual smoke test in Step 5 did not use that script and relied on `dashboard/` being the CWD, matching the script's own convention.

## Known Sample-Database Default Problem

Confirmed, unchanged, not fixed in this task: `ROLE_OS_PROJECTS_DB_PATH` — the canonical Project Intelligence database backing `projects`, `ai_sessions`, `ai_session_snapshots`, and therefore Resume Work, Project Memory, and Mission Control — defaults to a path under `samples/role_os_sample/00_SYSTEM/`, a fixture/demo location, while every other real-runtime-data table (workspace, assets, ecosystem, session) already correctly defaults under `var/role_os_dashboard/`. This is the single highest-leverage fix identified by the architecture proposal's Migration Strategy step 1 and is explicitly scoped as **Phase 1 — Task 2**, not addressed here.

## Current Startup Method

Canonical path (per `scripts/Start-RoleOS.ps1`, intended entry point `Start ROLE OS.bat`):
1. Resolve repo root from the launcher script's own location.
2. Probe `http://127.0.0.1:8000/health` — reuse if already running.
3. Resolve a Python interpreter (prefers `dashboard/.venv` or repo-root `.venv`).
4. Verify dependencies against `dashboard/requirements.txt`.
5. Re-anchor all five `ROLE_OS_*_DB_PATH` env vars to the repo root (not `dashboard/`).
6. Refuse to start if the Knowledge DB (`role_os.db`) is missing.
7. Launch `uvicorn app.main:app --host 127.0.0.1 --port 8000` from `dashboard/` as a minimized background process, log to `dashboard/var/...` (launcher-owned log paths, distinct from the app's own `var/role_os_dashboard/`).
8. Poll `/health` for up to 30s, then open the browser.

Test suite invocation (per `pyproject.toml`): `pytest` from the repo root, with `testpaths = ["tests", "dashboard/tests", "builder/tests"]` and `pythonpath = ["dashboard", "builder"]`.

## Startup Smoke Test

Performed manually (not via the `.ps1` launcher, to avoid touching the launcher's own PID/log files) from `dashboard/`:

```
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

- `GET /health` → `200 OK`, body: `{"status":"ok","app":"ROLE OS","version":"1.1.0","database_connected":false}`
- `GET /` → `200 OK`, 6,178-byte HTML response (dashboard home rendered successfully)
- `GET /mission-control` → `200 OK`, valid JSON; notably returned `"data_freshness":{"last_scan":"2026-08-11T13:12:22Z","hours_since_scan":674.7,"stale_threshold_hours":24,"is_stale":true}` — a live, empirical confirmation of the exact silent-staleness risk both the audit and architecture proposal flagged (the field exists and is correctly computed; nothing in the UI layer was checked for whether it renders this to a human, which remains out of scope for Task 1 and is Phase 1 — Task 5's concern).
- The process was terminated cleanly afterward (`taskkill /F`); no orphaned background process remains; no PID file was left behind (none was created, since the launcher script itself — which manages the PID file — was not used).
- Side effect: this request path caused a real write to `var/role_os_dashboard/role_os_assets.db` (see SQLite Database Inventory note above) — the app was not run with any isolating environment override, so it operated against real runtime data, as it would in normal use. `database_connected: false` in the health payload appears to describe the Knowledge DB (`role_os.db`) connection check specifically, not the app's overall ability to serve; this was not investigated further in Task 1.

**Result: the application starts and serves successfully from a clean checkout at the current baseline commit, with default configuration.**

## Test Baseline

Command: `pytest tests dashboard/tests builder/tests -q` (matches `pyproject.toml`'s `testpaths` exactly, full suite, no exclusions).

- Collected/run: **1,304**
- Passed: **1,304**
- Failed: **0**
- Skipped: **0**
- Errors: **0**
- Warnings: none reported
- Duration: **2,201.51s (36m41s)**

No exclusions were needed — the full suite ran to completion cleanly. The 36-minute duration is notably long for ~1,300 tests; not investigated further in Task 1 (candidate follow-up, not a Phase 1 blocker).

## Known Pre-Existing Issues

(Carried forward from the audit and architecture proposal, not fixed here)

- Canonical `projects.db` defaults to a fixture path instead of `var/role_os_dashboard/` (see above; Phase 1 Task 2).
- `var/role_os_alpha/` has no documented relationship to `samples/role_os_sample/` (Decisions Required From Role, item 2 in the architecture proposal).
- `decisions_adapter.py`'s fallback ecosystem-decisions data is frozen at 2026-07-29/30 with no visible staleness indicator in any template (Phase 1 Task 5).
- Empirically confirmed this session: Mission Control's own `data_freshness.is_stale` is currently `true` (674.7 hours since last scan) — the backend already knows the data is stale; whether any template renders that fact was not checked.
- `project-dashboard.html` and `assets/role-master/` remain undecided (Decisions Required From Role, items 1 and 3).
- `var/discovery_reports/documents/` has no current consumer (Decisions Required From Role, item 6).
- Full test suite runtime (~37 minutes) is unusually long; cause not investigated.

## Safety Constraints for Phase 1

- No database schema, default path, or migration may change except as explicitly scoped in Phase 1 Task 2.
- No template or router changes outside the task they're scoped to (Tasks 4/5/8).
- `project-dashboard.html` and `assets/role-master/` must not be moved, edited, or deleted until Role approves the archiving decision (Task 6).
- `var/role_os_alpha/` must not be merged or deleted until Role decides its fate.
- Every Phase 1 task should re-run at least the affected slice of this test suite before being considered done; a full-suite re-run at the end of Phase 1 is recommended given today's clean 1,304/1,304 baseline.
- The stray worktree at `C:/tmp/role_os_baseline_validation` should not be pruned or deleted without Role's explicit instruction, even though it appears unrelated and harmless.

## Exact Next Task

Phase 1 — Task 2: Fix Sample Database Default

## Post-Baseline Note (added after Task 2, baseline content above left unchanged)

Task 2 fixed the "Known Sample-Database Default Problem" described above. See `docs/PHASE_1_TASK_2.md` for the full record. Summary: `dashboard/app/config.py`'s five sample-defaulting fields (`db_path`, `projects_db_path`, `advisor_db_path`, `imports_db_path`, `extraction_db_path`) now default under `var/role_os/` instead of `samples/role_os_sample/00_SYSTEM/`; environment-variable overrides (including explicit sample selection for tests/demos) are unaffected. `var/role_os_dashboard/`'s already-correct paths (workspace/session/assets/ecosystem) and `var/role_os_alpha/` were intentionally left untouched — their consolidation remains Task 3's scope.
