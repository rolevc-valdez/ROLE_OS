# Role OS 2.0 — Phase 1 Task 8B

## Objective

Implement Task 8's approved "A — SMALL AND SAFE" navigation simplification: reduce the 13-item flat sidebar into ~5 conceptual clusters (Mission Control, Projects, Knowledge, Session, Settings) without deleting, unregistering, or renaming any router, route path, or deep link.

## Previous Navigation

13 flat, ungrouped sidebar items (`dashboard/app/templates/index.html`): Mission Control, Dashboard, Session, Projects, Workspace, Cockpit, Knowledge, Explorer, Advisor, Graph, Knowledge Graph, Assets, Settings — re-verified directly (not assumed from the Task 8 report) before editing; matched exactly.

## New Primary Navigation

The same 12 remaining `<li class="nav-item" data-nav="...">` elements, **byte-identical `data-nav` values and click behavior**, now visually grouped under 4 new non-interactive `<li class="nav-group-label">` headers:

- **Mission Control** (standalone, unchanged, still first)
- **Projects** — Projects, Workspace, Cockpit
- **Knowledge** — Knowledge, Explorer, Advisor, Graph, Knowledge Graph
- **Session** — Session
- **Settings** — Assets, Settings

**Dashboard** (v2) no longer has a sidebar entry — demoted per Task 8's recommendation. Its route (`GET /dashboard/summary`) and `renderDashboardPage()` are completely unchanged; Mission Control's Portfolio Ranking section now carries a "See full metrics →" link to it, in the exact same `link-btn`/`data-nav` pattern the page already used for its existing "Open Workspace →" link.

## Destination Mapping

| Cluster | Items | Backing routes | Code change |
|---|---|---|---|
| Mission Control | (itself) | `/mission-control` | None |
| Projects | Projects, Workspace, Cockpit | `/pi/projects`, `/workspace`, project-detail routes | Grouping only |
| Knowledge | Knowledge, Explorer, Advisor, Graph, Knowledge Graph | `/knowledge`, `/explorer`, `/advisor/*`, `/graph`, `/conversation-graph` | Grouping only |
| Session | Session | `/session/*` | Grouping only |
| Settings | Assets, Settings | `/assets`, `/settings/*` | Grouping only |

**Correction found during implementation** (Step 1's explicit instruction not to rely solely on the Task 8 report): Task 8's analysis assumed Import/Extraction needed a new discoverable home under Settings. Re-inspecting `app.js` directly during this task found their real UI (`#import-panel`, a working upload form calling `/import/chatgpt`; extraction's delete/run-extraction controls) **already lives inside `renderKnowledge()`** — i.e. already discoverable, already under the Knowledge cluster this task keeps as a primary destination. No change was needed or made for Import/Extraction discoverability.

## Routes Preserved

All 32 routers, all route paths, all `app.js` route-table entries (`home`, `mission-control`, `dashboard`, `session`, `cockpit`, `projects`, `project`, `dproject`, `workspace`, `knowledge`, `explorer`, `phub`, `advisor`, `graph`, `conversation-graph`, `assets`, `settings`) are byte-identical to before this task. Verified: `git diff --stat -- dashboard/app/main.py` is empty.

## Deep-Link Compatibility

Every hash route tested directly reachable and unchanged: `#/dashboard` (still resolves to `renderDashboardPage`, just no longer in the sidebar), `#/project/{id}`, `#/dproject/{id}`, `#/phub/{id}`, `#/cockpit/{id}`, and all 12 remaining sidebar destinations. New: a drill-down-to-cluster active-state map (`DRILLDOWN_PARENT_NAV`) makes `project`/`dproject`/`phub` — which have never had their own sidebar entry — highlight the "Projects" `nav-item` instead of leaving the sidebar unhighlighted, so grouping doesn't make these existing drill-downs feel disconnected from the new "Projects" cluster (Step 9). This only changes which existing element gets the `.active` class; it introduces no new route.

## Router Registration

Before: 32. After: 32. Verified via `grep -c "app.include_router" dashboard/app/main.py` before and after, and via a new test asserting this count directly against `main.py`'s own source.

## Tests

New file `dashboard/tests/test_navigation_simplification.py` (8 tests): router count unchanged, Mission Control still canonical landing, sidebar groups appear in the approved order, Dashboard removed from the sidebar but its route/link preserved, every remaining sidebar item has a live backing route, Import/Extraction already discoverable, drill-down-to-cluster highlighting present, no sample/`role_os_alpha` dependency introduced.

One pre-existing test needed updating (not a regression — it asserted the exact old behavior this task intentionally changes): `test_dashboard_ui.py: test_sidebar_includes_dashboard_nav_item` → renamed `test_dashboard_route_reachable_though_no_longer_in_primary_sidebar`, now asserting the route still works and is intentionally absent from the sidebar `<nav>`, referencing this task's doc.

Regression slice run (`mission_control`, `dashboard_ui`, `sprint5_ui`, `sprint4_ui`, `workspace_sprint`, `navigation`, plus a broader `_ui`/`app_js` keyword pass): **all passing**, see completion report for exact totals. The full ~1,300-test/37-minute suite was not run — the affected area (frontend templates/JS/CSS only, zero backend change) doesn't justify it, per this task's own instruction.

## Runtime Safety

All validation used `fastapi.testclient.TestClient` against the existing, already-isolated test configuration (`conftest.py`'s per-session temp databases) — no live server was started against canonical runtime data for this task, since the change is entirely frontend (templates/JS/CSS) and TestClient validation is sufficient and safer. Verified directly: `var/role_os_dashboard/role_os_workspace.db` and `role_os_session.db` mtimes are unchanged from before this task began. **No runtime or user data was modified.**

## Files Changed

- `dashboard/app/templates/index.html` — sidebar regrouped into 5 clusters; Dashboard `<li>` removed
- `dashboard/app/static/js/app.js` — `DRILLDOWN_PARENT_NAV` + `updateActiveNav()` extended; "See full metrics →" link added to Mission Control's Portfolio Ranking heading
- `dashboard/app/static/css/layout.css`, `dashboard/app/static/css/components.css` — `.nav-group-label` styling (spacing in `layout.css`, color/typography in `components.css`, matching the existing design-system file split)
- `dashboard/tests/test_navigation_simplification.py` — new, 8 tests
- `dashboard/tests/test_dashboard_ui.py` — one test updated to match the intentional new behavior
- `docs/PHASE_1_TASK_8B.md` — this file

No router, service, schema, or database file changed.

## Known Limitations

- The sidebar still renders all 12 non-Mission-Control items at once (grouped, not collapsed) — a future task could make groups collapsible if the list still feels long, but that would be a genuine UI-framework addition, which this task's brief explicitly said not to build.
- `project_ecosystem`/`impact_analysis` remain without any UI destination (Task 8's UNCERTAIN classification, deliberately not resolved here per Step 8's explicit "do not promote them into primary navigation merely to solve this task").

## Exact Next Task

Phase 1 — Task 9: Discovery Report Artifacts
