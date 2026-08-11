# 16 — Dashboard 2.0, Sprint C2: Completion Report

Scope executed: replace the legacy zero-centric Dashboard with an
executive dashboard powered by `ProjectContext` and the existing Home/
Advisor/Activity/Assets/Session/Knowledge/Workspace services. No parallel
aggregation engine, no Discovery/Workspace architecture changes, no
Mission Control, no LLM calls, no browser automation, no scanned-file
writes. No version bump, no commit, no tag.

## 1. The problem

The Sprint 7 Dashboard showed `GET /import/metrics` -- Explorer's own
counts of *extracted knowledge objects* (Project/Person/Task/Decision/
Idea/Document/Asset entities pulled out of imported ChatGPT
conversations). Those numbers were honestly zero whenever no conversation
had been imported, even though the real workspace already had adopted
projects, commits, sessions, and recommendations, all already served
correctly elsewhere in the app (Home, Workspace, Advisor, Cockpit). This
was a wrong-data-source bug, not a missing-data problem.

## 2. Architecture

```
GET /dashboard/summary
        │
        ▼
app.dashboard.service.build_dashboard_summary()   (new, composition only)
        │
        ├─ project_context.builder                (workspace + manual PI projects)
        ├─ workspace.service.get_home_portfolio     (Continue Work ranking, recent commits/assets)
        ├─ workspace.advisor.generate_recommendations (Needs Attention -- +1 new rule)
        ├─ workspace.service.list_activity_feed      (Recent Activity, already deduplicated)
        ├─ workspace.service.list_project_assets     (Recent Assets)
        └─ app.db (knowledge_db)                     (Recent Knowledge -- separate domain)
```

No new persisted store. No new scoring engine -- every number is a
`sum`/`len`/group over data another service already computed.

## 3. Files created

- `dashboard/app/dashboard/__init__.py`, `dashboard/app/dashboard/
  service.py` -- the composition module.
- `dashboard/app/routers/dashboard.py` -- one endpoint, `GET /dashboard/
  summary`.
- `dashboard/tests/test_dashboard_v2.py` -- 11 new tests.

## 4. Files modified

- `dashboard/app/main.py` -- registers the new router.
- `dashboard/app/workspace/advisor.py` -- adds `rule_snapshot_blocker`
  (the one genuinely missing evidence type the brief asked for: a
  blocker recorded in a project's latest AI session snapshot) to the
  existing eleven-rule set.
- `dashboard/app/static/js/app.js` -- `renderDashboardPage` and its
  legacy helpers (`dashboardMetricsHtml`, `renderDashboardMetrics`,
  `renderDashboardRecentConversations`, `renderDashboardRecentObjects`,
  `renderDashboardStatus`) fully replaced, not left underneath the new
  page.
- `dashboard/tests/test_dashboard_ui.py` -- rewritten for the new page
  (the old assertions tested the removed implementation).

## 5. Metrics and their sources

| Card | Source |
|---|---|
| Adopted Projects | `len(all_contexts)` (workspace-adopted + manual PI, deduped by discovery link) |
| Healthy / Warning / Critical | `ProjectContext.health` tier counts |
| Needs Attention | `len(home.projects_needing_attention)` |
| Dirty Repositories | `ProjectContext.git.is_dirty` count |
| With Next Action | `ProjectContext.next_action.text` truthy count |
| Active AI Sessions | `ProjectContext.latest_ai_session.status == "active"` count |
| Recent Snapshots | `ai_snapshot`-type events in the Recent Activity feed |
| Reusable Assets | `workspace.service.list_project_assets`, `reusable` flag |
| Knowledge Cards | `app.db.list_projects()` summed counts |
| Recent Commits | `git_commit`-type events in the Recent Activity feed |

## 6. Tests and results

11 new tests in `test_dashboard_v2.py` plus 10 rewritten in
`test_dashboard_ui.py` prove: the endpoint uses `ProjectContext`; real
adopted projects move cards off zero; health/dirty-repo/next-action counts
match the canonical per-project data exactly (recomputed independently via
the public API in each test, not assumed); Recent Activity is
deduplicated; Needs Attention items carry canonical `project_context`;
empty states are honest; the legacy `/import/metrics`-backed rendering
path is gone from `renderDashboardPage`; manual and discovered projects
both populate the dashboard. Full suite: **920 passed**. ruff
(`--select E9,F`) clean. black clean. JS syntax valid.

## 7. Live verification

Ran the real dashboard against the real ROLE OS workspace:

- `Adopted Projects: 7` (not 0); `Healthy: 3`, `Critical: 2`, `Warning: 2`;
  `Dirty Repositories: 2`; `Recent Commits: 6`.
- ROLE_OS and ROLE Commerce Factory both appeared correctly across summary
  cards, Portfolio Status, and Continue Work (ROLE_OS was the Continue
  Work suggestion, with a real next action, a real snapshot, and reasons;
  ROLE Commerce Factory appeared in Healthy, Active, and Launch-ready).
- Needs Attention listed real, evidence-backed items (dirty tree on
  `role-ecosystem`/`ROLE_OS`, near-completion on ROLE Commerce Factory,
  hardcoded-path risk on `ROLE_KNOWLEDGE_OS`), each linking to canonical
  project identity.
- Clicked Resume Work from the Dashboard: navigated to Cockpit, created/
  marked an AI session current, opened `https://claude.ai` -- fully
  functional, end to end.
- Zero application console errors on the Dashboard or Cockpit page. No
  scanned project file was touched (all writes were to the existing
  Workspace/Projects SQLite stores, as before).

## 8. Remaining limitations

- **Pre-existing data-quality artifact observed, not fixed**: "ROLE
  Commerce Factory" exists as two separate project rows (one discovery-
  linked, one purely manual with no `discovery_item_id`), so it appears
  twice in Portfolio Status groups. Deduplicating by name was deliberately
  not attempted (unreliable heuristic); this belongs to the PI/Workspace
  identity model, not this sprint.
- Active/Inactive and Launch-ready groups only cover discovered/adopted
  projects (manual projects have no discovery evidence for activity age
  or commercial readiness) -- honestly left out rather than guessed.
- No Mission Control, no cross-project dependency view, no LLM-assisted
  prioritization -- all explicitly out of scope for this sprint.

## 9. Recommendation for C3

1. Resolve the duplicate-project data-quality issue found live (likely a
   PI/Workspace identity bridging gap predating this sprint).
2. Consider a CI-level architectural guard (a lint rule or test) that
   fails when a new project-oriented route is added without embedding
   `ProjectContext`, closing the gap C1B's own report flagged as
   unresolved.
3. If Mission Control is prioritized next, design it as a further
   composition over `ProjectContext`/`workspace.advisor`/dashboard
   summary — the same pattern this sprint and C1B established — rather
   than a new engine.
