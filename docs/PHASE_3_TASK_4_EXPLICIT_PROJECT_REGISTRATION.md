# Role OS 2.0 — P3.4 Explicit Project Registration

*Implementation record. Lets Role register one isolated project folder by path (e.g. `C:\Users\rolev\bolsa-de-trabajo`) without widening Discovery roots and without adopting it. No new database file, no new Git subsystem, no Discovery-root change.*

**Baseline:** `4822221` (P3.3 complete — the actual P3.3 completion commit, verified via `git log`). Working tree was clean and in sync with `origin/main` at start.

## Recovery / Pre-flight

- Read `CURRENT_STATE.md`, `NEXT_ACTIONS.md`, `docs/ROLE_OS_2_PHASE_3_SCOPE.md`, and the P3.1–P3.3 docs. No discrepancy: P3.3 COMPLETE, P3.4 the next task.
- **`New folder` (repo root) — removed.** Verified empty (no files, no hidden entries), untracked (`git ls-files` empty; Git does not track empty dirs), and referenced by no code/config/script — only mentioned as "empty, junk" in the historical `audits/ROLE_OS_1X_AUDIT.md` (left unchanged). Removed with `rmdir`. No other cleanup.

## Architecture Reused

Inspected Discovery (`app/discovery/*`), Workspace (`app/workspace/service.py`, `db.py`), adoption overlay (`adopted_projects`), identity (`app/discovery/identity.compute_item_id`, `app/workspace/identity`), path validation (`app/discovery/roots`), manifest detection (`detectors/operational_manifest.py`, tech markers), Project Context and Mission Control.

Key finding: every Workspace consumer (lists, hierarchy, adopt, Project Context, Mission Control) reads folders through a single function, `service._cached_projects()`, which previously returned only the last root scan. Registration therefore plugs in at exactly one point:

- **Same database** (`role_os_workspace.db`) — one new table, `registered_projects`. No new DB file.
- **Same analysis pipeline** — `analyze_folder` → `read_git_info` → `classify` → `assign_boundaries`, i.e. the stages `run_audit` applies to each candidate, run on the one registered folder only. No new Git inspection code.
- **Same identity** — `compute_item_id(root_path)`, so a registered folder has the same kind of id as a discovered one and every existing `/workspace/discovered/{id}/…` endpoint (review, adopt, notes, override) works on it unchanged.
- **Same adoption** — the existing `adopted_projects` overlay and `POST /workspace/discovered/{id}/adopt`.

## Registration Model

`registered_projects` (created by the idempotent schema script; additive):

| column | meaning |
|---|---|
| `id` | `compute_item_id(root_path)` — stable Workspace identity |
| `root_path` | resolved, real-cased absolute path |
| `path_key` (UNIQUE) | `normcase(normpath(path))` — one row per real directory |
| `source` | `explicit` |
| `registered_at` | UTC timestamp |
| `snapshot_json` / `snapshot_at` | that one folder's Discovery analysis (same shape as a scan-cache entry), refreshed on every rescan |
| `last_error` | set when a refresh finds the folder missing/unreadable; the last good snapshot is kept |

`_cached_projects()` = root scan cache + registered snapshots whose `path_key` the scan did not already find. Each merged item now carries `registration_source: "discovery" | "explicit"`; `GET /workspace/summary` gains `projects_registered`.

Survives restart (persisted row), computer restart, and Discovery refresh (a rescan replaces only the scan cache, then re-analyzes registered folders). Independent of `ROLE_OS_DISCOVERY_ROOT(S)`.

## Registration vs Adoption

**DISCOVERY ≠ REGISTRATION ≠ ADOPTION** is preserved:

- Registering writes only a `registered_projects` row. It creates **no** `adopted_projects` row, sets **no** domain/client/kind, and resolves **no** canonical PI project.
- The registered folder appears in Workspace as an ordinary *Discovered / not adopted* top-level item (badge "Discovered", `registration_source: explicit`).
- Adoption remains the separate, explicit existing step. Mission Control, Project Context lists, Advisor, Activity, Assets etc. all use `adopted_only=True`, so a registered-but-not-adopted folder never reaches *What should I do now*, *Active Projects* or *Pending Work*. After adoption, normal behavior applies (tested).

Flow: **REGISTER PROJECT → enter path → VALIDATE (inspect, read-only) → REVIEW card → Register → (later, explicitly) Adopt**.

## Path Safety

`registration.normalize_path` (read-only: resolve/stat/scandir):

- empty → `empty`; relative → `not_absolute` (never resolved against the server's CWD); surrounding quotes stripped (pasted "Copy as path").
- nonexistent → `not_found`; file → `not_directory`; permission/OS errors → `inaccessible` (reported, never raised as 500).
- `Path.resolve(strict=True)` normalizes `.`/`..`, slashes and casing to the real folder path; duplicates compared by `normcase(normpath)` → case-insensitive, trailing-slash-insensitive.
- **Too broad → refused:** a drive root, the user profile (`Path.home()`), or any ancestor of it (e.g. `C:\Users`). Registering `C:\Users\rolev` is rejected with "register the specific project folder inside it instead".
- Only the registered folder itself is analyzed (bounded inventory walk, same limits as Discovery). Its parent is never listed, so siblings are never discovered (tested: a sibling next to the registered folder does not appear).
- A folder already found by a Discovery root is reported as `discovered_via_root` and **not** registered again (409 `already_discovered`) — one identity per folder.
- A folder inside an already-known project is allowed but flagged (`inside_known_project`) in the review.

## Git and Non-Git

Both are supported — the existing model does not require Git. For Git repos the review shows repository YES, remote, branch and last commit, all from the existing read-only `read_git_info`. A non-Git folder is registered as-is; if Discovery's own boundary rules would not have promoted it (no markers), the explicit registration is recorded as boundary evidence ("explicitly registered by Role as a project folder") and the item is treated as a top-level project, with Discovery's original verdict still listed.

Manifests reported (not parsed): tech markers (`package.json`, `pyproject.toml`, …) relative to the folder, `README.md`, `ROLE_PROJECT.md` if present (existence only — ingestion is P3.5), and `.role-os/project-status.json` if the existing operational-manifest detector found one.

## API

All under the existing `/workspace` router (no new router):

| method | path | behavior |
|---|---|---|
| POST | `/workspace/registrations/inspect` `{path}` | validate + inspect, **persists nothing**; always 200 with `valid` / `error{code,message}` |
| POST | `/workspace/registrations` `{path}` | register; 201; 400 invalid path; 409 `already_registered` / `already_discovered` |
| GET | `/workspace/registrations` | list registrations with review data, `registered_at`, `last_error` |
| DELETE | `/workspace/registrations/{item_id}` | unregister; 404 unknown; 409 `has_workspace_data` |

Review/adopt of a registered item uses the existing `/workspace/discovered/{id}` endpoints.

## UI

Workspace page (`#/workspace`):

- **Register Project** button next to *Rescan Workspace* → dialog with a plain text input *Project folder:* and **Validate** (Enter also validates). A text path is the v1 mechanism: a browser page cannot safely open an unrestricted native folder picker, and no file-system hack was built.
- **Review card:** Name, Path, Git repository YES/NO (+branch), Remote, Last commit, Detected manifest, Existing Role OS identity, Registration status, Adoption status, and an "inside a known project" warning when relevant.
- **Action:** *Register* (with "not adopted, will not appear in Mission Control until you adopt it"); once registered: *Adopt* with optional Domain (default **Unclassified**) / Kind / Client — nothing pre-selected or guessed — and *Unregister*.
- **Registered project folders** card (only when any exist): name, folder, adoption, registered date (or ⚠ last refresh error), *Review* and *Unregister* (hidden once adopted).

Verified live in the browser: the page, the registered-folders card and the review dialog render with bolsa-de-trabajo's real data. **Adopt was not clicked.**

## Unregister

Deletes only the `registered_projects` row. Never deletes the folder, its files, or Git history (tested: file tree size/mtime identical, `git log` intact). Blocked with 409 `has_workspace_data` while the item is adopted, has a canonical Role OS project id, or has notes — those relationships are never silently orphaned; un-adopting/cleanup must go through a separate workflow. Unregistering a folder that is also under a Discovery root leaves the discovered item in place.

## Tests

`dashboard/tests/test_explicit_project_registration.py` — **27 tests**: valid path inspected without persisting; nonexistent path; file vs directory; empty/relative; user profile / its parent / drive root refused; quoted path; duplicate; trailing slash + case variants; Windows normalization (`.\`, casing) to the real path; already-discovered folder not double-registered; Git metadata (remote/branch/commit) reused; non-Git folder; survives settings reload + unrelated rescan; does not widen Discovery roots and does not surface siblings; refresh keeps a registration whose folder vanished (with `last_error`); no auto-adopt / no classification / no overlay row; adoption through the existing flow; unregister leaves filesystem and Git history intact; unregister blocked for adopted and for noted items; unknown id; full API flow (inspect/register/409/400/list/discovered/delete/404); API 409 for adopted; **excluded from Mission Control until adopted, then appears in Active Projects**; existing discovery flow unchanged (`registration_source = discovery`); UI strings.

Each test uses its own workspace DB under `tmp_path` and clears the `lru_cache`d `get_settings()` before and after — the first full run exposed that without the cache clear the API tests wrote into the session-wide test DB and broke 10 order-dependent Workspace tests; fixed in the fixture, not by changing any other test.

Results: focused 27/27; **full suite 1,453 passed, 0 failed** (`tests/`, `builder/tests/`, `dashboard/tests/`; 1,426 before + 27). No existing test was modified.

## Runtime DB Isolation

SHA256 of all 15 runtime DB files (10 under `var/`, 5 in the external `ROLE_KNOWLEDGE_OS\00_SYSTEM\`) were identical before and after both full test runs.

## Live Validation — `C:\Users\rolev\bolsa-de-trabajo`

Server restarted with the repo's own Stop/Start scripts (it was already running before the task; left running afterwards).

- **Inspect:** valid; name `bolsa-de-trabajo`; Git YES, branch `main`; remote `git@github.com:rolevc-valdez/bolsa-de-trabajo.git`; last commit 2026-09-02 "Fix homepage counters to show only active non-expired posts"; manifest `package.json`; classification Mixed Project; no existing Role OS identity; not registered / not adopted. `GET /workspace/registrations` still `[]` after inspect.
- **Safety, live:** `C:\Users\rolev` → `too_broad`; a nonexistent path → `not_found`.
- **Register:** `201`, item id `d560e18f1f2b3339`. Re-registering as `c:\users\rolev\BOLSA-DE-TRABAJO\` and `C:/Users/rolev/bolsa-de-trabajo/` → `409 already_registered`.
- **After a full server restart:** registration still listed; `/workspace/discovered/d560e18f1f2b3339` → `adopted: false`, `registration_source: explicit`, `domain: null`; shown in Workspace top-level list as not adopted; summary `projects_found 23` (scan unchanged), `projects_adopted 5`, `projects_registered 1`.
- **Mission Control:** the string "bolsa" appears nowhere in `GET /mission-control`; Active Projects remain the five ROLE PERSONAL projects; portfolio lists the same five.
- **Discovery roots:** `ROLE_OS_DISCOVERY_ROOTS` unset, default root unchanged; scan cache unchanged (root `…\1 - IA PROJECTS`, 2026-09-10, 23 projects). No rescan was run against canonical data.
- **The bolsa repository was only read.** Its one pre-existing local modification (`tsconfig.tsbuildinfo`, mtime 2026-09-02) predates this task.

## Runtime / User Data Modified

- `var/role_os_dashboard/role_os_workspace.db`: new table `registered_projects` (schema auto-created) + **exactly one row** — bolsa-de-trabajo (`id d560e18f1f2b3339`, `source explicit`, `registered_at 2026-09-23T21:30:51Z`, snapshot 4,039 bytes, no error). `adopted_projects` unchanged: 5 rows, all `ROLE PERSONAL / project / active`; no row for bolsa. `integrity_check` ok.
- `var/role_os_dashboard/role_os_assets.db`: changed by the app's ordinary asset-cache refresh while running (same side effect recorded in P3.3), not by this task's code.
- Nothing else changed (other 13 DB checksums identical). bolsa-de-trabajo was **not adopted and not classified**. FERREVOLT, Kontoor, Unger, yt-dlp, Cobalt were not registered.

## Remaining Limitations

- Path entry is text only (no native folder picker in a browser app).
- If a registered folder later also falls under a configured Discovery root with a different path casing, the discovered entry wins and any adoption made under the registered id would need re-linking; registering a folder already under a root is refused precisely to avoid this.
- Registered folders are re-analyzed on every rescan (cheap for a handful; not designed for hundreds).
- No bulk registration; no UI to un-adopt (unchanged pre-existing gap).
- `ROLE_PROJECT.md` is only reported when present — ingestion/schema is P3.5.
- Next: **P3.5 — External Project Manifest / ROLE_PROJECT.md** (NOT STARTED).
