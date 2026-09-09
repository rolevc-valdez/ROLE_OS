# Role OS 2.0 — Runtime Data Map

Status as of 2026-09-09. This is a factual inventory produced by Phase 1 Task 3. **No database was copied, moved, merged, or deleted while producing this document.** `var/role_os/` was **not created** — see "Data NOT Migrated" for why.

## Canonical Runtime Root

`var/role_os/` — the default `dashboard/app/config.py` and `scripts/RoleOS.Common.ps1` resolve into when nothing else is configured (Phase 1 Tasks 2 and 2B, commits `a61b226`, `a5379c6`). This default is correct and unchanged by Task 3.

**Critical finding that changes what "canonical" means in practice**: on this machine, `ROLE_OS_WORKSPACE_DIR` is set **persistently** (both `User` and `Machine` scope, i.e. via `setx`) to an **external, sibling folder outside this repository**:

```
C:\Users\rolev\My Drive (rolevc@gmail.com)\1 - IA PROJECTS\ROLE_KNOWLEDGE_OS
```

This means `var/role_os/` is the canonical **fallback-when-nothing-is-configured** location — correct for a fresh clone, CI, or a machine with no workspace set up yet — but it is **not** where this machine's real, live data actually lives or should live. `ROLE_KNOWLEDGE_OS\00_SYSTEM\` is the real canonical data location for the Knowledge/Projects/Advisor/Imports/Extraction family on this machine, exactly as `INSTALLATION.md` and `docs/product/DECISIONS.md` always intended — it is external to the repo by design and must not be copied into `var/role_os/` (doing so would create a second, silently-diverging copy of live data, which is precisely what the `ROLE_OS_WORKSPACE_DIR` decision was designed to prevent).

## Canonical Runtime Databases

| Database | Path (default, no override) | Purpose | Source | Status |
|---|---|---|---|---|
| `role_os.db` | `var/role_os/role_os.db` | Knowledge Graph (`knowledge_cards`) | None — real data lives externally at `ROLE_KNOWLEDGE_OS\00_SYSTEM\role_os.db` (1,069 conversations/cards) | INITIALIZE ON FIRST USE (empty until Builder runs against this path, or `ROLE_OS_WORKSPACE_DIR`/`ROLE_OS_DB_PATH` is set) |
| `role_os_projects.db` | `var/role_os/role_os_projects.db` | Project Intelligence (`projects`, `ai_sessions`, snapshots, etc.) | None safe (see Ambiguities) | INITIALIZE ON FIRST USE (auto-creates schema + seeds default workspaces per `app/projects/db.py`) |
| `role_os_advisor.db` | `var/role_os/role_os_advisor.db` | Advisor recommendations | None safe (see Ambiguities) | INITIALIZE ON FIRST USE |
| `role_os_imports.db` | `var/role_os/role_os_imports.db` | ChatGPT import metadata | None — no real data found anywhere with non-zero rows | INITIALIZE ON FIRST USE |
| `role_os_extraction.db` | `var/role_os/role_os_extraction.db` | Extracted knowledge objects | None — no real data found anywhere with non-zero rows | INITIALIZE ON FIRST USE |

None of these five files exist under `var/role_os/` as of this writing. `var/role_os/` itself does not exist. This is correct: every candidate source is either external and must stay external (see above), fixture-only, or ambiguous (see below) — there is no LOW-RISK copy to execute per Step 6's criteria.

## Existing Legacy Data Locations

| Location | What's really there | Real launcher runs? |
|---|---|---|
| `ROLE_KNOWLEDGE_OS\00_SYSTEM\` (external, sibling of the repo) | The real Knowledge/Projects data — see Database Provenance | **Yes** — `launcher.log` proves real `Start ROLE OS.bat` runs from 2026-07-30 through 2026-08-21 using this exact folder |
| `dashboard/var/role_os_dashboard/` | Real workspace/session/ecosystem/asset-cache data (14 real adopted projects, 7 registry projects, 3,810 cached assets) | **Yes** — same `launcher.log`/`role_os.pid`/`uvicorn.*.log` files live here, proving this is genuinely where the real launcher's uvicorn process runs from (`-WorkingDirectory dashboard\`) and where its CWD-relative `var/role_os_dashboard/...` paths actually resolve to |
| `var/role_os_dashboard/` (repo root) | A much smaller, largely empty parallel copy (0 adopted projects, 0 scan cache, only 581 cached assets vs. 3,810) | **Likely not** — see "A newly discovered gap" below |
| `dashboard/samples/role_os_sample/00_SYSTEM/` | Debris created by *this session's own* Phase 1 Task 1 smoke test | No — accidental, see below |
| `var/role_os_alpha/` | Ambiguous — see role_os_alpha Assessment | Unclear |
| `samples/role_os_sample/00_SYSTEM/` | The committed demo fixture | N/A — fixture, not runtime |
| `var/discovery_reports/documents/` | Generated report artifacts (`documents_audit.json`/`.md`), no current router consumer (per the audit) | N/A — not a database |

### A newly discovered gap (flagged, not fixed in this task)

`scripts/RoleOS.Common.ps1: Resolve-RoleOSDatabaseEnv` only re-anchors five environment variables (`ROLE_OS_DB_PATH`, `..._PROJECTS_DB_PATH`, `..._ADVISOR_DB_PATH`, `..._IMPORTS_DB_PATH`, `..._EXTRACTION_DB_PATH`) to absolute, repo-root-anchored paths before starting uvicorn. It does **not** re-anchor `ROLE_OS_WORKSPACE_DB_PATH`, `ROLE_OS_SESSION_DB_PATH`, `ROLE_OS_ASSETS_DB_PATH`, `ROLE_OS_ECOSYSTEM_DB_PATH`, or `ROLE_OS_ASSET_THUMBNAIL_CACHE_DIR`. Since `dashboard/app/config.py` defaults these five to the CWD-relative string `var/role_os_dashboard/...`, and the real launcher starts uvicorn with `-WorkingDirectory dashboard\`, every real launcher-driven run has actually been reading and writing `dashboard/var/role_os_dashboard/...` — not the repo-root `var/role_os_dashboard/...` that `docs/PHASE_1_BASELINE.md` and `docs/ROLE_OS_2_ARCHITECTURE_PROPOSAL.md` both (reasonably, from static code reading alone) assumed was "already correct" runtime data. **This is a real, unresolved defect, parallel to the one Task 2B fixed for the other five variables — but it is out of Task 3's scope** (Task 3 covers the `var/role_os/` family only) and is not fixed here. Recommended as an urgent near-term follow-up (a "Task 2C"-shaped fix), not blocking Task 4.

A second, smaller contributor: `dashboard/tests/conftest.py` isolates ten of the twelve dashboard-owned DB paths with `tempfile.mkdtemp()`-based env vars, but does **not** set `ROLE_OS_ASSETS_DB_PATH` or `ROLE_OS_ECOSYSTEM_DB_PATH`. Running the test suite from the repo root (as `pyproject.toml` specifies) therefore reads/writes the real repo-root `var/role_os_dashboard/role_os_assets.db` and `role_os_ecosystem.db` for any test that exercises Assets OS. This session's own Phase 1 Task 1/2 pytest runs are the most likely explanation for the repo-root `role_os_assets.db`'s recent growth and low, test-fixture-shaped row count (581 cache rows of small `tmp_path`-scale assets, vs. `dashboard/var/role_os_dashboard/`'s 3,810 real cached assets from actual real-tree scans). Flagged, not fixed — fixing test isolation is outside Task 3's "runtime data directory" scope.

## role_os_alpha Assessment

`var/role_os_alpha/role_os_advisor.db` (14 `recommendations` rows) and `var/role_os_alpha/role_os_projects.db` (7 `workspaces`, **7 `projects`**, 6 `capabilities`, 4 `capability_consumers`, 3 `dependencies`) were compared byte-for-byte and row-for-row against every other candidate:

- **Not a duplicate of the sample fixture**: checksums differ from `dashboard/samples/.../role_os_advisor.db`, and the project names are completely different — alpha's `projects` table lists **`ROLE OS`, `ROLE MASTER`, `SUPER FACIL`, `RoleValdez`, `Kontoor`, `Unger`, `Charcos`** — every single name is a specific, real-sounding project/brand name (several match names that recur throughout `audits/ROLE_OS_1X_AUDIT.md` and the Role Ecosystem's own documentation), with **zero generic placeholder rows** ("Test Project," "Active Project," etc.). This is the opposite pattern from every fixture/debris database found (see below), which all mix in obvious placeholder names.
- **Not a subset of `ROLE_KNOWLEDGE_OS`'s real data**: `ROLE_KNOWLEDGE_OS\00_SYSTEM\role_os_projects.db` lists a different 10 names (`Role Test Project, ROLE Commerce Factory, ROLE MASTER, role-ecosystem, ROLE_KNOWLEDGE_OS, ROLE_OS, ROLE Commerce Factory, Active Project, Paused Project, Quiet Project`) — only `ROLE MASTER` and (loosely) `ROLE OS`/`ROLE_OS` overlap with alpha's list. `Kontoor`, `Unger`, `Charcos`, `SUPER FACIL`, and `RoleValdez` (as a project name, distinct from `RoleValdez.com`/`role-ecosystem`) appear **nowhere else** in any database inspected.
- **Older than everything else with real data**: file mtimes are 2026-07-23, seven days before `ROLE_KNOWLEDGE_OS`'s earliest recorded launcher run (2026-07-30).
- **Has real relational structure the "real" workspace's projects.db mostly doesn't populate**: 6 `capabilities` + 4 `capability_consumers` + 3 `dependencies` rows — `ROLE_KNOWLEDGE_OS`'s copy has zero rows in all three of those tables.

**Conclusion: `var/role_os_alpha/` cannot be classified as disposable demo data with confidence.** It reads far more like either (a) a genuine, real early snapshot of Project Intelligence data from **before** `ROLE_OS_WORKSPACE_DIR`/`ROLE_KNOWLEDGE_OS` existed as the chosen real-workspace convention, manually exported/copied to `var/role_os_alpha/` for a specific "alpha demo" purpose that then took on a life of its own, or (b) a deliberately hand-built rich demo dataset that happens to reuse real project/brand names for realism. **This is exactly the kind of ambiguity Step 5 says to stop on rather than merge or guess.** No action taken; flagged below as a Role decision.

## role_os_dashboard Assessment

Two directories currently hold `role_os_workspace.db`/`role_os_assets.db`/`role_os_ecosystem.db`/`role_os_session.db`-shaped data (`workspace`/`session` only exist under one of them):

| | `dashboard/var/role_os_dashboard/` | `var/role_os_dashboard/` (repo root) |
|---|---|---|
| `role_os_workspace.db` | 14 `adopted_projects`, 1 `workspace_scan_cache` row | 0 rows in both tables |
| `role_os_session.db` | 7 `registry_projects`, 0 `sessions` | *(file does not exist here)* |
| `role_os_ecosystem.db` | 0 `relationship_overrides` | 0 `relationship_overrides` |
| `role_os_assets.db` | 3,810 `asset_cache`, 92 `asset_overrides` (1.06 MB) | 581 `asset_cache`, 10 `asset_overrides` (180 KB) |
| Corroborating evidence | `launcher.log` (real runs 2026-07-30 → 2026-08-21), `role_os.pid`, `uvicorn.out/err.log` all present here | No launcher artifacts present |

**This is real, substantive user data, and it lives in `dashboard/var/role_os_dashboard/`, not the repo-root copy.** Per the newly discovered CWD-anchoring gap above, this is the actual, historically-accumulated runtime state.

**Decision for Task 3: (C) treat this family as separate subsystem storage by design, and take no action.** Per the task brief's own instruction ("prefer NO move unless architecture clearly requires it") and the explicit scope boundary (Task 3 covers `var/role_os/` only), this family is left exactly where it is — in both locations — pending Role's decision on how to close the CWD-anchoring gap (which directory should become authoritative, and how to reconcile the repo-root copy's small amount of real-shaped cache growth from this session's own test runs). No file was moved, copied, or deleted in either location.

## Sample / Fixture Data

- `samples/role_os_sample/00_SYSTEM/` — the committed demo fixture (`role_os.db`: 1 `knowledge_cards` row; `role_os_projects.db`: 6 `workspaces`, 0 `projects`). Untouched. Correctly reachable only via explicit `ROLE_OS_DB_PATH`/`ROLE_OS_WORKSPACE_DIR` selection (Task 2B).
- `dashboard/samples/role_os_sample/00_SYSTEM/*.db` (4 files: advisor, extraction, imports, projects) — **not a real fixture location at all**. This entire directory was created by this session's own Phase 1 Task 1 startup smoke test, which ran `uvicorn` with CWD `dashboard/` *before* Task 2's config fix landed, so the then-current sample-fixture default (`samples/role_os_sample/00_SYSTEM/...`, CWD-relative) resolved to `dashboard/samples/...` instead of the real repo-root `samples/...`. Confirmed via row content: `role_os_projects.db` here contains a mix of generic placeholder projects (`app-a`, `Manual Only Test`, `Paused Project` ×3, `Active Project` ×2, `Bare Project`) *and* real folder names picked up by a live Discovery Engine scan of this machine's actual `1 - IA PROJECTS` directory (`ROLE Commerce Factory`, `ROLE MASTER`, `role-ecosystem`, `ROLE_KNOWLEDGE_OS`, `ROLE_OS`) — i.e. real folder names, but freshly (and accidentally) re-adopted under new, disconnected `projects.id` values today, not genuine curated data. **This is accidental debris, disclosed here and in `docs/PHASE_1_BASELINE.md`; not deleted per this task's explicit "do not delete" instruction, but flagged for cleanup.**

## Database Provenance

| Database | Path | Rows (key tables) | Verdict |
|---|---|---|---|
| `role_os.db` | `ROLE_KNOWLEDGE_OS\00_SYSTEM\` | 1,069 conversations / knowledge_cards | **REAL** — the actual Knowledge Graph |
| `role_os_projects.db` | `ROLE_KNOWLEDGE_OS\00_SYSTEM\` | 10 projects, 6 ai_sessions, 1 snapshot | **REAL** — the actual live Project Intelligence DB, last touched 2026-08-21 (matches last launcher run) |
| `role_os_advisor.db` | `ROLE_KNOWLEDGE_OS\00_SYSTEM\` | 0 recommendations | REAL location, currently empty (never run against real data) |
| `role_os_imports.db`, `role_os_extraction.db` | `ROLE_KNOWLEDGE_OS\00_SYSTEM\` | 0 rows | REAL location, unused so far |
| `role_os_workspace.db`, `role_os_session.db` | `dashboard/var/role_os_dashboard/` | 14 adopted_projects, 7 registry_projects | **REAL** |
| `role_os_assets.db` | `dashboard/var/role_os_dashboard/` | 3,810 asset_cache rows | **REAL** |
| `role_os_ecosystem.db` | either `var/role_os_dashboard/` location | 0 rows | Empty everywhere; not yet used |
| `role_os_projects.db`, `role_os_advisor.db` | `var/role_os_alpha/` | 7 projects (unique real-sounding names), 14 recommendations | **AMBIGUOUS — real or realistic demo, cannot confirm; see role_os_alpha Assessment** |
| `role_os.db`, `role_os_projects.db` | `samples/role_os_sample/00_SYSTEM/` | 1 card, 0 projects | FIXTURE (committed, intentional) |
| everything under `dashboard/samples/role_os_sample/00_SYSTEM/` | — | mixed placeholder + accidentally-readopted real names | **DEBRIS** (this session's own Task 1 side effect) |
| `role_os_assets.db`, `role_os_ecosystem.db` | `var/role_os_dashboard/` (repo root) | 581 asset_cache (small); 0 relationship_overrides | Mostly test-run pollution (see conftest.py gap above), not meaningfully real |

## Data Copied During Phase 1 Task 3

**None.** Every candidate either must stay where it correctly already is (`ROLE_KNOWLEDGE_OS`, `dashboard/var/role_os_dashboard/`), is a fixture that must stay a fixture (`samples/`), or is ambiguous/debris that Step 5/6 explicitly say not to act on unilaterally (`var/role_os_alpha/`, `dashboard/samples/...`).

## Data NOT Migrated

- `ROLE_KNOWLEDGE_OS\00_SYSTEM\*.db` — real, live, external, already correctly selected via the persistent `ROLE_OS_WORKSPACE_DIR`. Copying any of it into `var/role_os/` would create a second, silently-diverging copy of live data — exactly what the architecture's `ROLE_OS_WORKSPACE_DIR` decision exists to prevent. **Left entirely untouched.**
- `dashboard/var/role_os_dashboard/*.db` — real, live, but a different subsystem family (workspace/session/assets/ecosystem) not in scope for the `var/role_os/` canonical root this task establishes. **Left entirely untouched**, pending the CWD-anchoring gap decision above.
- `var/role_os_alpha/*.db` — ambiguous provenance (see Assessment above). **Left entirely untouched** pending Role's decision.
- `samples/role_os_sample/00_SYSTEM/*.db` — intentional fixture. **Left entirely untouched.**
- `dashboard/samples/role_os_sample/00_SYSTEM/*.db` — accidental debris from this session. **Left entirely untouched** (not deleted, per this task's explicit instruction); flagged for a future cleanup task.
- `var/role_os_dashboard/*.db` (repo root) — small amount of real-shaped but likely test-polluted cache data. **Left entirely untouched.**

Because no source was judged safe to copy, `var/role_os/` was **not created**. This is consistent with Step 6/7: only LOW-RISK migrations with clear provenance execute automatically, and none existed.

## Ambiguities / Role Decisions Needed

1. **`var/role_os_alpha/` disposition** — is this genuine early real data (pre-dating the `ROLE_OS_WORKSPACE_DIR` convention) that should be preserved/archived deliberately, or a hand-built demo dataset using real names that's safe to keep as-is or retire? Needs Role's memory of what `scripts/seed_alpha_demo.py` was actually run against and when.
2. **The CWD-anchoring gap for workspace/session/assets/ecosystem paths** — should `scripts/RoleOS.Common.ps1` be extended to re-anchor these five variables too (making `<RepoRoot>\var\role_os_dashboard\` authoritative for real launcher runs, matching what the docs have always assumed), or should the documented "real" location be corrected to `dashboard\var\role_os_dashboard\` instead? Either fix reconciles two currently-diverging copies of real data; picking wrong risks orphaning the 14 real adopted projects currently sitting under `dashboard/var/role_os_dashboard/`.
3. **`dashboard/samples/role_os_sample/00_SYSTEM/` cleanup** — safe to delete once Role confirms these four files are indeed this session's own debris (row-content evidence strongly supports this, but the decision to delete is intentionally left to Role per this task's constraints).
4. **`var/role_os_dashboard/` (repo root) cleanup or reconciliation** — once decision #2 is made, the repo-root copy's small amount of real-shaped-but-likely-test-polluted data will need a decision (discard, or verify nothing genuinely real is only there).
5. **`dashboard/tests/conftest.py`'s isolation gap** for `ROLE_OS_ASSETS_DB_PATH`/`ROLE_OS_ECOSYSTEM_DB_PATH` — worth a small, separate test-infra fix so running the suite never again touches real runtime data, whichever location is chosen as authoritative.

## Backup / Preservation Status

No file was copied, moved, renamed, or deleted while producing this document or its inventory. Every SQLite file inspected passed `PRAGMA integrity_check` (`ok`) — see per-database notes above; none showed `.db-wal`/`.db-shm`/`.db-journal` leftovers. All reads used `sqlite3.connect("file:...?mode=ro", uri=True)` (read-only connection mode) to guarantee no write could occur during inspection.

## Initialization Behavior

Confirmed by reading the relevant `db.py` modules (not by triggering real initialization against production paths, per this task's safety posture — see Testing/Validation in the completion report):

- `role_os_projects.db`, `role_os_advisor.db`, `role_os_imports.db`, `role_os_extraction.db` — all four dashboard-owned modules (`app/projects/db.py`, `app/advisor/db.py`, `app/imports/db.py`, `app/extraction/db.py`) call `db_path.parent.mkdir(parents=True, exist_ok=True)` then `CREATE TABLE IF NOT EXISTS ...` in their `get_connection()`. **Safe to leave absent** — first real use against `var/role_os/` (or wherever configured) creates the directory and schema cleanly, exactly as already proven by `dashboard/tests/test_config.py: test_projects_db_still_auto_creates_at_the_new_default_location` (Phase 1 Task 2).
- `role_os.db` (Knowledge) — `app/db.py` is read-only: no `CREATE TABLE`, `get_connection()` raises `DatabaseUnavailableError` if the file doesn't exist, and `/health`'s `database_connected` field reports `false` via `database_exists()` rather than crashing. **Safe to leave absent** — the existing failure mode is already clear and non-silent (Phase 1 Task 2's `test_missing_knowledge_db_at_new_default_fails_clearly_not_silently`).

## Exact Next Task

Phase 1 — Task 4: Mission Control Landing Experience
