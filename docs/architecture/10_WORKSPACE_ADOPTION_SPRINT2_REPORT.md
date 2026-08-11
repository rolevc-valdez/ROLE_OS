# 10 — Workspace Adoption, Sprint 2: Completion Report

Scope executed: Workspace Adoption exactly as specified — a Workspace page
over the read-only Discovery Engine, Adopt/Ignore/Review actions, a small
non-duplicating overlay record, Rescan, summary stats, and additive
Projects-page integration. No Advisor/Graph/Health/Mission Control changes.

## 1. Files created / changed

```
dashboard/app/config.py                     # + workspace_db_path, discovery_root settings
dashboard/app/workspace/__init__.py         # module docstring / "don't duplicate metadata" contract
dashboard/app/workspace/db.py               # SQLite: workspace_scan_cache, adopted_projects
dashboard/app/workspace/models.py           # Pydantic request/response schemas
dashboard/app/workspace/service.py          # scan caching + cache/overlay merge + CRUD
dashboard/app/routers/workspace.py          # /workspace/* API
dashboard/app/main.py                       # + include_router(workspace.router)
dashboard/app/templates/index.html          # + "Workspace" sidebar nav item
dashboard/app/static/js/app.js              # + renderWorkspacePage and friends; renderProjectsList
                                             #   extended to merge in adopted projects
dashboard/tests/conftest.py                 # + isolated ROLE_OS_WORKSPACE_DB_PATH tmp dir
dashboard/tests/test_workspace_db.py        # 14 tests
dashboard/tests/test_workspace_service.py   # 16 tests
dashboard/tests/test_workspace_api.py       # 13 tests
dashboard/tests/test_workspace_ui.py        # 5 tests
```

No existing file inside `app/discovery/`, `app/projects/`, `app/advisor/`,
`app/graph/`, or any `/pi/*` router was modified. `role_os_projects.db`'s
schema is untouched — Workspace Adoption lives entirely in its own new
SQLite file.

## 2. Architecture used

**Identity, not duplication.** A discovered folder has no database id
until you decide to track it, so every Workspace item's id is
`sha1(root_path)[:16]` — deterministic, computed with no I/O, stable
across rescans as long as the folder doesn't move. `adopted_projects` rows
are keyed by that same id. This is what makes "don't duplicate metadata"
concrete rather than a slogan: the overlay table has exactly six editable
columns (`priority`, `business_value`, `status`, `tags`, `notes`,
`ignored`/`adopted` flags) plus `root_path` for identity — no `name`, no
`health_score`, no `classification`, no git fields. Every read (`GET
/workspace/discovered`, `/discovered/{id}`, `/adopted`) re-merges the
cached scan with the overlay at request time; nothing about a project's
real-world state is ever "frozen" into a row by adopting it.

**Cache, not live-scan-per-request.** Scanning `1 - IA PROJECTS` takes
~7-8s (measured in Sprint 1). Requiring a full filesystem walk on every
page load would make the Workspace page unusably slow, so `workspace_scan_
cache` holds exactly one row (a JSON dump of the last `ScanResult`'s
projects), refreshed only by the explicit "Rescan Workspace" action —
matching requirement #8 exactly (a button, not automatic background
polling).

**Deviation from the original §14/§15 proposal, deliberately:** the
approved architecture doc's §14 said to add `root_path` etc. columns
directly onto the `projects` table. This sprint's actual instructions were
more specific and, I think, better: keep discovered projects in their own
overlay table entirely separate from `role_os_projects.db`, so manually-
created Projects are **structurally** guaranteed unaffected (not just
"tested to still work") — you cannot break `/pi/projects` by anything in
`app/workspace/`, because it isn't in the same file, table, or code path.
I followed the newer, more specific instruction over the earlier proposal
text; `08_IMPORT_ENGINE_PROPOSAL.md`'s status line now notes this.

## 3. Requirement-by-requirement

| # | Requirement | Where |
|---|---|---|
| 1 | New Workspace page | Sidebar nav item + `#/workspace` route, `renderWorkspacePage()` in `app.js` |
| 2 | Configurable root path | `Settings.discovery_root` (env `ROLE_OS_DISCOVERY_ROOT`, defaults to this checkout's own parent dir) + per-call `root` override on `POST /workspace/rescan` |
| 3 | Name/Folder/Type/Git/Health/Confidence/Move Risk per project | `WorkspaceItem` model + `renderWorkspaceRowHtml()` table row |
| 4 | Adopt/Ignore/Review buttons | `data-workspace-adopt/ignore/review` + `wireWorkspacePageActions()` |
| 5 | Adopt creates a linked record, no metadata duplication, filesystem stays source of truth, overlay = priority/business value/status/tags/notes/ignore only | `app/workspace/db.py` schema + `service._merge()` (see §2 above) |
| 6 | Ignore hides the project | `ignored` flag filters it out of the default `GET /discovered` list (`include_ignored=false` by default) |
| 7 | Review opens project details | `openWorkspaceReviewDetail()` — reuses the existing detail overlay modal, shows the full discovery signal set (languages, docs, tests, move-risk/recommendation reasons) plus any notes |
| 8 | Rescan Workspace | `workspace-rescan-btn` → `POST /workspace/rescan` (calls the real `discovery.service.run_audit`, unmocked) |
| 9 | Last Scan / Projects Found / Projects Adopted / Ignored Projects | `GET /workspace/summary` + the four summary cards at the top of the page |
| 10 | Projects page shows adopted projects | `renderProjectsList()` now also fetches `/workspace/adopted` and renders those cards (labeled "Discovered") alongside manual ones |
| 11 | Manual projects still work | `/pi/projects` and its router/db/UI are byte-for-byte untouched; verified by the full existing suite passing plus a dedicated new test (`test_manual_projects_api_still_works_after_workspace_feature`) |
| 12 | Migration if needed | None needed — see §4 |
| 13 | Tests | 48 new tests (see §5) |
| 14 | Full regression suite | 694/694 passing (up from 651 at the end of Sprint 1) |

## 4. Why no migration was needed

`role_os_projects.db`'s schema (the `projects` table and everything else
in `app/projects/db.py`) was not touched at all — no column added, no
table added, no row shape changed. Workspace Adoption's two tables
(`workspace_scan_cache`, `adopted_projects`) live in a **new** SQLite file
(`role_os_workspace.db`), created idempotently via `CREATE TABLE IF NOT
EXISTS` the same way every other domain's first release in this codebase
works (advisor, imports, extraction — none of those needed a `schema_
migrations` entry either; that mechanism exists in `app/projects/db.py`
specifically for changing an *existing, populated* table, e.g. the v1.3→
v1.4 AI Workspace → AI Sessions copy). If a future sprint changes the
shape of `adopted_projects` after real user data exists in it, that would
be the first time this domain needs a tracked migration.

## 5. Tests and results

48 new tests across four files, all real (no mocks anywhere — every test
either hits the real, unmodified `discovery.service.run_audit` against a
synthetic folder tree it creates itself, or asserts against the real
`app.js`/`index.html` served by the real app):

| File | Count | Covers |
|---|---|---|
| `test_workspace_db.py` | 14 | overlay CRUD, adopt/ignore/unignore interactions and idempotency, partial-patch semantics (doesn't clobber other fields), notes append, scan-cache round-trip and overwrite |
| `test_workspace_service.py` | 16 | real Discovery Engine runs (unmocked) against tmp folder trees, overlay survives a rescan, ignore/unignore visibility, review-detail full signal set, summary counts, `/adopted` reshaping, id stability, no-filesystem-modification guarantee |
| `test_workspace_api.py` | 13 | full HTTP flow (rescan → discover → adopt/ignore/review/unignore), 404s on unknown ids, 400 on an invalid root, `/workspace/adopted` shape, and — the requirement #11 check — that `/pi/projects` still works after all of the above |
| `test_workspace_ui.py` | 5 | nav item present, route registered, all four summary stats/rescan button/per-item fields/action buttons present in the served JS, Projects-page merge logic present including the fixed first-run-onboarding condition |

Full suite: **694 passed, 0 failed** (`pytest -q` from repo root).

**A real bug caught while wiring the frontend, fixed before this report:**
the sidebar's `[data-nav]` click handling was originally attached once, at
boot, directly to the fixed sidebar `<li>` elements — it would not have
fired for a `[data-nav="workspace"]` element rendered later inside
`#view-root` (e.g. a "Discovered" project card linking to the Workspace
page), since that content is replaced on every navigation. Fixed by
routing `[data-nav]` clicks inside `#view-root` through the same click-
delegation block already used for `[data-open-project]`/`[data-open-card]`.
Covered by `test_view_root_delegation_handles_data_nav_from_rendered_
content`.

## 6. Real-data verification (no mock data, no fake projects)

In addition to the automated suite (which uses synthetic-but-real folder
trees, not mocks), I ran the actual feature end-to-end against the real
`1 - IA PROJECTS` folder, through the real `TestClient` + real app, with
an isolated overlay database so nothing about this smoke test polluted
the committed sample data:

```
rescan status: 200
{'root': 'C:\\...\\1 - IA PROJECTS', 'projects_found': 17, 'projects_adopted': 0, 'projects_ignored': 0}

17 discovered projects (01_BRAND_CORE, 02_PROMPT_SYSTEM, ROLE_OS, ...)

adopted: ROLE_OS -> 200 True high
summary: {'projects_found': 17, 'projects_adopted': 1, 'projects_ignored': 0}
/workspace/adopted: [{'name': 'ROLE_OS', 'workspace': 'Discovered', 'health_score': 79,
                       'priority': 'high', 'business_value': 'high', 'move_risk': 'high', ...}]
manual /pi/projects still works: 0 rows
```

`ROLE_OS` — this very project — was discovered, classified, health-scored
(79), and adopted with zero data typed in by hand, confirming the exact
outcome the original architecture proposal's Definition of Done asked for.

## 7. Limitations / things to know before the next sprint

- **`OTROS - no proyectos` is still not excluded.** Sprint 1's report
  flagged this and it remains true here: the Workspace page will happily
  list it as a discoverable/adoptable folder. This sprint didn't touch
  `scanner.py`, so the fix is still pending — the "Ignore" button is the
  workaround for now (one click, persists across rescans since the
  overlay row isn't wiped by re-scanning).
- **The Workspace page's "Review" detail is read-only and does not
  support editing notes/tags from within the modal** — notes/tags exist in
  the API (`POST /discovered/{id}/notes`, `PATCH /discovered/{id}`) and
  are exercised by tests, but the UI only surfaces *reading* them today,
  not a form to add one. Minimal by design for this sprint; a natural
  Sprint 3 UI addition.
- **`/workspace/adopted`'s `health_score` can be `None`** for a project
  the Discovery Engine couldn't score at all (e.g. a folder with no git
  history and no readable mtime — see Sprint 1's `health.py` `None`-signal
  case); the Projects-page card renders `0` in that case via a fallback,
  which slightly understates "unknown" as "zero" — worth a dedicated
  "unscored" badge if this comes up in practice.
- **One scan cache, one root.** There's exactly one cached scan at a time
  (`workspace_scan_cache` is a singleton row). Rescanning a different root
  than last time fully replaces the cache and thus what the Workspace page
  shows — there's no multi-root history or comparison view. Fine for this
  single-user, single-machine tool; would need a real schema change to
  support multiple tracked roots.
- **Health score reflects Sprint 1's filesystem-only signals**, not
  anything from Project Intelligence's own Health Score engine
  (`app/projects/health/`) — the two are intentionally not unified yet;
  that unification is explicitly Sprint 3/4 territory (Advisor/Health
  wiring), not this sprint.

## 8. Recommended Sprint 3

Per the same rollout plan this proposal has followed since Sprint 1:

1. **Exclusion-list support in `scanner.py`** (still the top carry-over
   item from Sprint 1's report) — now doubly motivated, since it would
   also stop `OTROS - no proyectos` from cluttering the Workspace page.
2. **Advisor/Health wiring** (§12 of the original proposal): feed real
   commit dates and filesystem activity into `app/projects/health/
   commits.py` (documented no-op today) for *adopted* projects
   specifically — Workspace Adoption already computed a Health Score
   per project, Sprint 3's job is deciding how/whether that becomes the
   same number Project Intelligence shows, or a second, clearly-labeled
   number.
3. **Notes/tags editing UI** inside the Review modal (see §7).
4. **Mission Control ranking view** (§13 of the proposal) — now has real
   data to rank: adopted projects' health/confidence/move-risk/last-
   modified are all sitting in the cache, unused by any "what should I
   work on today" view yet.
