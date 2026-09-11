# Role OS 2.0 — Phase 1 Task 8

Status: **analysis only**. No router, endpoint, service, template, or database was changed in producing this document.

## Objective

Determine how Role OS's ~32 registered routers and 13 primary-navigation destinations should be organized around Mission Control's now-canonical three-question landing experience — a small primary navigation with powerful drill-downs — without deleting or destabilizing any working capability.

## Current Navigation Inventory

**Registered routers** (`dashboard/app/main.py`, in registration order): 32 `app.include_router(...)` calls.

**Sidebar (primary navigation) destinations** (`dashboard/app/templates/index.html`'s `data-nav` items, all always visible): 13 — Mission Control (labeled, `data-nav="home"`), Dashboard, Session, Projects, Workspace, Cockpit, Knowledge, Explorer, Advisor, Graph, Knowledge Graph (`conversation-graph`), Assets, Settings.

**Drill-down-only routes** (in `app.js`'s router table but not in the sidebar — reached only by clicking through from another page): `project` (canonical project detail), `dproject` (discovered-project detail), `phub` (Project Hub).

**Registered routers with no dedicated nav destination at all** (JSON APIs only, or consumed inside another page): `pi_reconciliation`, `pi_collections`, `pi_capabilities`, `pi_dependencies`, `pi_health`, `pi_ai_workspace`, `pi_ai_sessions`, `pi_workspaces`, `advisor_search`, `imports`, `extraction`, `project_context`, `project_ecosystem`, `impact_analysis`, `executive_decision`, `launcher`, `search`, `knowledge` (single-card lookup), `health`, `ui` (the SPA shell + 2 small JSON helpers). This is already a large group — evidence that "route registered, but not a primary nav item" is already this codebase's normal, working pattern, not a change Task 8 would be introducing.

## Router Inventory

| Router | URL prefix | Primary user function | In sidebar? | Directly composed into Mission Control? |
|---|---|---|---|---|
| `health` | `/health` | Liveness/version check | No | No |
| `projects` (Milestone 1) | `/projects` | Knowledge cards grouped by project name | No | No |
| `search` | `/search` | Global header search box | No (header widget) | No |
| `knowledge` | `/knowledge/{id}` | Single knowledge-card lookup | No | No |
| `ui` | `/`, `/ui/*` | Serves the SPA shell itself | N/A (delivery mechanism) | N/A |
| `pi_workspaces` | `/pi/workspaces` | Workspace grouping (header selector) | No | No |
| `pi_reconciliation` | `/pi/projects/reconciliation/*` | Merges discovered + manual project duplicates | No | No (used by Projects list) |
| `pi_projects` | `/pi/projects` | Canonical project CRUD (capabilities/dependencies/health/tags/notes) | Via "Projects"/Cockpit | No |
| `pi_collections` | `/pi/projects/{id}/collections` | Deliverables/decisions/todos/prompts CRUD | Via project detail | No |
| `pi_capabilities` | `/pi/projects/{id}/capabilities` | Project capability records | Via project detail | No |
| `pi_dependencies` | `/pi/projects/{id}/dependencies` | Project dependency graph edges | Via project detail | No |
| `pi_health` | `/pi/projects/{id}/health` | Health score computation | Via project detail badges | No |
| `pi_ai_workspace` | `/pi/projects/{id}/ai-workspace` | Legacy (v1.3) AI workspace fields | Via project detail | No |
| `pi_ai_sessions` | `/pi/projects/{id}/ai-sessions` | AI Sessions + Snapshots + Timeline | Via Cockpit/Resume Work | Indirectly (Project Memory reads this data) |
| `advisor` | `/advisor` | Rule-based recommendation engine | Yes | No |
| `advisor_search` | `/advisor/search` | Search over imported conversations/extracted knowledge | No | No |
| `graph` | `/graph` | Knowledge Graph (Projects/Advisor/Builder data) | Yes | No |
| `imports` | `/import` | ChatGPT export import + Conversation Explorer | No | No |
| `extraction` | `/extraction` | Rule-based Person/Task/Decision/Idea extraction | No | No |
| `conversation_graph` | `/conversation-graph` | Second Knowledge Graph, over imported conversations | Yes ("Knowledge Graph") | No |
| `settings` | `/settings` | Config display, export/import preview, maintenance | Yes | No |
| `session` | `/session` | Start/End My Day, project registry, ecosystem decisions | Yes | Partially (`daily_session` card) |
| `launcher` | `/launcher` | AI Launcher (copy prompt, open assistant) | No (used in Session page) | No |
| `workspace` | `/workspace` | Discovery browsing, adoption, resume-work trigger | Yes | Yes (adoption data, freshness, activity feed) |
| `project_context` | `/project-context` | The one shared per-project composition service | No (backend only) | Yes (`all_project_contexts`) |
| `dashboard` (v2) | `/dashboard` | Executive summary / broad metrics view | Yes | No |
| `explorer` | `/explorer` | Universal cross-domain search | Yes | No |
| `assets` | `/assets` | Asset index/search/preview/overrides | Yes | Yes (shared filesystem walk via `request_scope()`) |
| `mission_control` | `/mission-control` | **The landing experience itself** | Yes (labeled "Mission Control") | — |
| `project_ecosystem` | `/project-ecosystem` | Inter-project relationship graph | No (backend only) | Indirectly (Executive Decision's `compute_relationships`) |
| `impact_analysis` | `/impact-analysis` | "If this changes, what else breaks?" | No (backend only) | No |
| `executive_decision` | `/executive-decision` | "What should I work on next?" scoring | No (backend only) | Yes (`get_executive_decision`) |

## Core vs Supporting Classification

Reuses `docs/ROLE_OS_2_ARCHITECTURE_PROPOSAL.md`'s own classification (Phase 0.5) rather than inventing a new one, extended to cover the routers that document didn't name individually:

**CORE** (the five-stage PROJECT → STATE → ACTION → CONTEXT → RESUME chain, or its direct data layer): `workspace` (adoption overlay + resume trigger), `pi_projects`/`pi_ai_sessions`/`pi_ai_workspace`/`pi_capabilities`/`pi_dependencies`/`pi_health`/`pi_reconciliation`/`pi_collections` (the canonical Projects DB the chain reads from), `project_context`, `mission_control`.

**DRILL-DOWN** (a deeper view of something Mission Control already summarizes, reached by clicking through, not a competing entry point): `projects` (nav item → list → project detail = Cockpit), Cockpit itself, `dproject`/`phub` detail views, `session` (Daily Session's full page vs. Mission Control's `daily_session` card), `dashboard` v2 (broader metrics vs. Mission Control's one decision).

**UTILITY**: `search`, `launcher`, `settings`, `ui`.

**ADMIN/DIAGNOSTIC**: `health`, `imports`, `extraction`.

**LEGACY/OPTIONAL** (per the architecture proposal's own "Optional Capabilities" section — independent, nothing in Core imports from them, only they import Core's outputs): `advisor`, `advisor_search`, `graph`, `conversation_graph`, `knowledge` (Milestone 1's standalone card lookup), `projects` (Milestone-1 grouped-cards endpoint — distinct from `pi_projects`).

**UNCERTAIN**: `project_ecosystem`, `impact_analysis` — genuinely useful (they feed Project Memory's bounded "related projects/impact" section per the architecture proposal) but have no dedicated UI destination of their own at all today; whether that's an intentional "backend-only, composed elsewhere" design or a gap worth a small drill-down is a judgment call, not evidence-clear either way.

## Overlap Analysis

Traced each candidate pair by actually reading what it returns/renders, not by name:

| Pair | Finding | Classification |
|---|---|---|
| Mission Control vs. Dashboard (v2) | Mission Control = one decision + three questions, composed once per request. Dashboard = a broader executive metrics grid (health dashboard, portfolio status) — genuinely different scope (breadth vs. one decision), not a duplicate. Its own code comment already says this: "Dashboard remains the deeper executive analytics view." | KEEP SEPARATE, but DEMOTE Dashboard from primary sidebar to a "See full metrics →" link reachable from Mission Control |
| Mission Control vs. Workspace | Workspace is where discovery/adoption/rescan/resume-work actually happen (the mechanism); Mission Control surfaces the *result* of that state. Not a duplicate — Workspace is upstream of Mission Control's data. | KEEP SEPARATE, primary nav |
| Project Memory vs. Resume Work | Not two things: Project Memory (`project_memory/service.py`) is the "what to say" assembler; Resume Work (`workspace/resume.py`) is the action that calls it. Confirmed in `docs/product/DECISIONS.md`. No overlap exists in code; this pair is not even two nav destinations. | N/A — not a real overlap |
| Project Context vs. project detail page | Project Context is the shared backend composer; "project detail"/Cockpit is its one UI rendering. Correctly one-to-one, not duplicative. | KEEP SEPARATE (one is backend, one is UI) |
| Operational Intelligence vs. Executive Decision | Different outputs from the same evidence: OI produces a *list* of recommendations (feeds Today's Focus/Needs Attention); Executive Decision picks *one* winner via a scoring/ranking pass on top of OI's own list (confirmed: `executive_decision/service.py` takes `operational_intelligence_recs` as an input, never recomputes). Layered, not duplicated. | KEEP SEPARATE (already correctly layered) |
| Ecosystem/Impact Analysis vs. decision views | Project Ecosystem computes relationships; Impact Analysis walks that graph; Executive Decision's `compute_relationships` call reuses Ecosystem's detector. All three compose, none duplicate the others' computation. Their shared trait: **none has a dedicated UI page** — all three are backend-only today. | HIDE FROM PRIMARY NAV (already true); no navigation change needed since they were never in it |
| Graph vs. Conversation Graph | Two genuinely independent knowledge graphs over different data (Project/Advisor/Builder data vs. imported-conversation data) — confirmed intentional in `main.py`'s own comments and `docs/product/DECISIONS.md`. | KEEP SEPARATE, but both are candidates to DEMOTE from top-level sidebar into a shared "Knowledge" or "Tools" group (see Step 5) |
| Discovery vs. Workspace/project inventory | Discovery is stateless filesystem truth (no persistence beyond a scan cache); Workspace is the adoption overlay on top of it. Already correctly separated per the architecture proposal — Discovery has no UI of its own; Workspace is its only consumer-facing surface. | N/A — not a real overlap, already correctly layered |

**No case required merging navigation, and no case revealed a router that duplicates another's actual computation.** The overlaps that exist are all intentional layering already documented elsewhere, not accidental duplication.

## Primary User Journey

The brief's proposed model —

```
MISSION CONTROL → PROJECT → STATE/CONTEXT → NEXT ACTION → RESUME WORK
```

— **fits the actual implementation exactly**, and already works end-to-end (verified live in Tasks 3D/4/5): Mission Control's Primary Focus card names a project → clicking it opens Cockpit/discovered-project detail (state/context: git info, health, latest snapshot, latest AI session) → the same card already shows the next action → the same card's "Resume Work →" button executes the resume chain. No implementation change is needed to make this journey real; it already is the real journey. Task 8's job is only to stop the *rest* of the router surface from visually competing with it in the sidebar.

## Proposed Primary Navigation

Target ~5 top-level destinations (evidence-based, not forced to a round number):

| Proposed item | Purpose | Backing route(s) | Nav entries folded underneath | Code change required? |
|---|---|---|---|---|
| **Mission Control** | Landing: the three questions + Resume Work | `/mission-control` | (none — already the landing page) | No |
| **Projects** | Adopt, browse, inspect, resume any project | `/workspace`, `/pi/projects`, `/project-context` | Workspace, Projects, Cockpit, discovered-project detail, Project Hub | No — these already share one conceptual flow; only relabeling/grouping in the sidebar |
| **Knowledge** | Browse imported ChatGPT history and its two graphs | `/knowledge`, `/graph`, `/conversation-graph`, `/advisor`, `/explorer` | Knowledge, Graph, Knowledge Graph, Advisor, Explorer | No — pure regrouping |
| **Insights** *(optional, only if Ecosystem/Impact are ever given a UI)* | Broader analytics: Dashboard v2, and (if ever surfaced) Ecosystem/Impact | `/dashboard`, `/project-ecosystem`, `/impact-analysis` | Dashboard | No |
| **Session** | Start/End My Day, ecosystem decisions | `/session`, `/launcher` | Session | No |
| **Settings** | Configuration, import/export, maintenance | `/settings`, `/import`, `/extraction` | Settings | No — Import/Extraction already have no nav entry; this only gives them one, nested |

Every proposed grouping is **information-architecture only** — a sidebar/menu change in `index.html`/`app.js`. Zero backend routers move, rename, or disappear.

## Router Disposition Matrix

| Router | Route | Purpose | 2.0 Classification | Primary nav? | Drill-down from | Keep registered? | Future action | Risk if hidden | Risk if removed |
|---|---|---|---|---|---|---|---|---|---|
| health | `/health` | Liveness check | ADMIN | No | — | Yes | KEEP | None | Breaks launcher's health probe |
| projects (M1) | `/projects` | Grouped knowledge cards | LEGACY | No | Knowledge | Yes | REVIEW | Low | Breaks Knowledge page's project filter |
| search | `/search` | Header search | UTILITY | No (header) | — | Yes | KEEP | None | Breaks header search box |
| knowledge | `/knowledge/{id}` | Card lookup | LEGACY | Yes | — | Yes | GROUP UNDER PARENT (Knowledge) | Low | Breaks Knowledge page |
| ui | `/`, `/ui/*` | SPA shell | — | N/A | — | Yes | DO NOT REMOVE | Breaks the entire app | Breaks the entire app |
| pi_workspaces | `/pi/workspaces` | Workspace selector | CORE | No | Header | Yes | KEEP | Breaks header filter | Breaks header filter |
| pi_reconciliation | `/pi/projects/reconciliation/*` | Dedupe discovered/manual | CORE | No | Projects list | Yes | KEEP | None (internal) | Breaks Projects dedup |
| pi_projects | `/pi/projects` | Canonical project CRUD | CORE | Via Projects/Cockpit | Projects, Cockpit | Yes | KEEP | Breaks project detail | Breaks project detail entirely |
| pi_collections | `/pi/projects/{id}/collections` | Deliverables/decisions/todos | CORE | Via project detail | Cockpit | Yes | KEEP | Loses a tab | Breaks Cockpit sections |
| pi_capabilities | `/pi/projects/{id}/capabilities` | Capability records | CORE | Via project detail | Cockpit | Yes | KEEP | Loses a tab | Breaks Cockpit sections |
| pi_dependencies | `/pi/projects/{id}/dependencies` | Dependency edges | CORE | Via project detail | Cockpit | Yes | KEEP | Loses a tab | Breaks Impact Analysis too |
| pi_health | `/pi/projects/{id}/health` | Health scoring | CORE | Via badges | Everywhere health shows | Yes | KEEP | Loses health badges | Breaks ranking/scoring everywhere |
| pi_ai_workspace | `/pi/projects/{id}/ai-workspace` | Legacy v1.3 fields | LEGACY | Via project detail | Cockpit | Yes | REVIEW (superseded by ai_sessions) | None | Possible data loss for old records |
| pi_ai_sessions | `/pi/projects/{id}/ai-sessions` | Sessions/Snapshots/Timeline | CORE | Via Cockpit | Resume Work | Yes | KEEP | Breaks Resume Work entirely | Breaks Resume Work entirely |
| advisor | `/advisor` | Recommendations | OPTIONAL | Yes | — | Yes | GROUP UNDER PARENT (Knowledge) | Loses "Daily Brief" | Breaks header Daily Brief button |
| advisor_search | `/advisor/search` | Search imported data | OPTIONAL | No | Advisor | Yes | KEEP | None | Breaks Advisor's search box |
| graph | `/graph` | Knowledge Graph | OPTIONAL | Yes | — | Yes | GROUP UNDER PARENT (Knowledge) | None | Removes a real feature |
| imports | `/import` | ChatGPT import | ADMIN | No | Settings | Yes | GROUP UNDER PARENT (Settings) | None (already hidden) | Breaks import pipeline |
| extraction | `/extraction` | Rule-based extraction | ADMIN | No | Settings | Yes | GROUP UNDER PARENT (Settings) | None (already hidden) | Breaks extraction pipeline |
| conversation_graph | `/conversation-graph` | Second Knowledge Graph | OPTIONAL | Yes | — | Yes | GROUP UNDER PARENT (Knowledge) | None | Removes a real feature |
| settings | `/settings` | Config/maintenance | UTILITY | Yes | — | Yes | KEEP | Loses config visibility | Breaks Settings page |
| session | `/session` | Daily Session | DRILL-DOWN | Yes | Mission Control's Daily Session card | Yes | GROUP UNDER PARENT (Session, kept top-level) | None (already summarized in MC) | Breaks Start/End My Day |
| launcher | `/launcher` | AI Launcher | UTILITY | No | Session page | Yes | KEEP | None | Breaks AI Launcher card |
| workspace | `/workspace` | Discovery/adoption/resume | CORE | Yes | — | Yes | KEEP (primary nav) | Breaks the core loop | Breaks the core loop |
| project_context | `/project-context` | Composition service | CORE | No | — | Yes | DO NOT REMOVE | Breaks everything that reads it | Breaks everything |
| dashboard (v2) | `/dashboard` | Executive metrics | DRILL-DOWN | Yes | Mission Control ("See full metrics") | Yes | DEMOTE FROM PRIMARY NAV | Low, reachable via link | Loses broad-metrics view |
| explorer | `/explorer` | Universal search | UTILITY | Yes | — | Yes | GROUP UNDER PARENT (Knowledge) | Low | Loses cross-domain search |
| assets | `/assets` | Asset index | CORE-adjacent | Yes | — | Yes | KEEP | None | Breaks Assets gallery + shared walk |
| mission_control | `/mission-control` | Landing experience | CORE | Yes | — | Yes | KEEP (top of nav) | Breaks the landing page | Breaks the landing page |
| project_ecosystem | `/project-ecosystem` | Relationship graph | SUPPORTING | No | — | Yes | REVIEW (candidate for a future drill-down) | None | Breaks Impact Analysis + Executive Decision's shared-assets pass |
| impact_analysis | `/impact-analysis` | Impact of change | SUPPORTING | No | — | Yes | REVIEW (candidate for a future drill-down) | None | Loses "what breaks if I change X" |
| executive_decision | `/executive-decision` | Decision scoring | CORE | No (feeds MC) | — | Yes | DO NOT REMOVE | Breaks Mission Control's "TODAY" card | Breaks Mission Control's "TODAY" card |

**Every "Future action" above is KEEP / GROUP UNDER PARENT / DEMOTE FROM PRIMARY NAV / REVIEW / DO NOT REMOVE.** Not one router is marked for removal, deprecation, or deletion.

## Deep-Link / Compatibility Risks

- Every router above is exercised by at least one existing test file (`dashboard/tests/test_*`) — removing or renaming any route would break test coverage, not just navigation.
- `app.js`'s `navigate(view, param)` writes real, shareable URL hashes (`#/project/{id}`, `#/dproject/{id}`, `#/cockpit/{id}`) — these are exactly the kind of "may be bookmarked" links Step 8 asks about. None of the changes proposed above touch route paths or hash values, only which items appear in the visible sidebar list (a CSS/DOM-order concern, not a routing concern).
- `scripts/`, `builder/`, and other Role Ecosystem repos do not call any dashboard HTTP route directly (confirmed throughout Phase 0/1) — no cross-repo compatibility risk exists.
- `/health` is polled by `scripts/RoleOS.Common.ps1`'s launcher — explicitly flagged `DO NOT REMOVE`.

**No deep link is broken by this proposal, because this proposal changes zero route paths.**

## Admin / Utility Grouping

A single secondary **"Settings"** grouping already exists (`/settings`) and already conceptually owns configuration/maintenance; the natural extension is folding `imports`/`extraction` under it as an "Import & Extraction" section (both are already absent from the primary sidebar today — this only gives them a discoverable home instead of zero UI entry point at all). `health` needs no user-facing grouping — it is a machine endpoint, not a page.

## Recommended Implementation Scope

If implemented, Task 8B should be scoped to exactly:

- Reorganize `dashboard/app/templates/index.html`'s sidebar markup and `app.js`'s nav-highlighting logic into grouped sections (e.g. collapsible "Projects", "Knowledge", "Settings" clusters) — a DOM/CSS/small-JS change only.
- Add one "See full metrics →" link from Mission Control's Dashboard-adjacent area to the existing `/dashboard`-backed page (already exists; just needs a link, matching the same pattern as the existing "Open Workspace →" link already on the Portfolio section).
- Add an "Import & Extraction" sub-section under Settings, linking to the already-existing (currently orphaned-from-nav) import/extraction pages if they have one, or exposing their existing API-only functionality through the Settings page's UI if they don't yet.
- **Zero** router registrations, endpoint signatures, service functions, or database schemas change.
- **Zero** route paths/hash values change (no deep link breaks).

## Task 8B Recommendation

**A — SMALL AND SAFE.**

Reason: every proposed change is confined to `index.html`'s sidebar markup and `app.js`'s DOM-rendering/highlighting code — no backend router is touched, no route path changes, no database is touched, and the Router Disposition Matrix above found zero routers warranting removal or deprecation. This is squarely a frontend information-architecture change, exactly the kind Task 8's brief asked to evaluate for, not an architectural or backend restructuring.

## Validation

- All 32 registered routers accounted for in the Router Inventory and Disposition Matrix above.
- All 13 sidebar nav destinations accounted for.
- Mission Control confirmed still the canonical landing route (unchanged; `ui.router`'s `/` route and `app.js`'s default-to-`home` behavior were only read, not modified, in this task).
- `git diff` confirms zero application source files changed by this task (verified below).
- No runtime database was opened for writing in this task (only read-only inspection of `main.py`, `index.html`, `app.js`, and prior task docs).
- No user data changed.

## Known Limitations

- `project_ecosystem`/`impact_analysis` having no dedicated UI destination is flagged as UNCERTAIN rather than resolved — a future task could decide whether they deserve a small drill-down (e.g. a "Related Projects" tab on Cockpit) or should stay backend-only indefinitely; this analysis does not force that decision.
- `pi_ai_workspace` (the superseded v1.3 field set, kept alongside v1.4's `pi_ai_sessions`) was flagged REVIEW rather than a definitive recommendation — determining whether any real project still has data only there requires a database query this analysis-only task did not perform (to avoid opening any database for inspection beyond what prior tasks already covered).

## Exact Next Task

Phase 1 — Task 8B: Navigation Simplification Implementation
