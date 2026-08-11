# 14 — Project Context, Sprint C1 (Consolidation): Completion Report

Scope executed: build one reusable service (`ProjectContext`) that
assembles everything a UI screen needs to describe a project, reusing
Discovery, Workspace Adoption, Project Intelligence, and Advisor exactly
as they already work. No rewrite of any of those four systems. No version
bump, no commit, no tag.

## 1. Architecture

```
                    ┌─────────────────────────────┐
                    │   app.project_context        │
                    │   (Sprint C1 -- NEW)          │
                    │                               │
                    │  build_project_context()      │
                    │  build_project_contexts_      │
                    │    for_workspace()             │
                    └───────────┬───────────────────┘
                                │ reads only, calls once each
        ┌───────────┬───────────┼───────────┬────────────────┐
        ▼           ▼           ▼           ▼                ▼
  identity.py   workspace    projects/db   workspace/    app.advisor.
  (Sprint 5)     .service    (PI Projects,  advisor.py    engine
  canonical id  .enrich_     AI Sessions,  (evidence-     (Epic 2,
  resolution    project_     Snapshots,    over-discovery reasons over
                item(),      Timeline)     rules)         manual PI data)
                get_item()

        ▲ unchanged, reused as-is                    ▲ unchanged, reused
        │                                             │
  ┌─────┴─────────────────────────────────────────────┴─────┐
  │  Consumers (Sprint C1 wiring, additive)                   │
  │  - GET /project-context/{id}   GET /project-context        │
  │  - Cockpit's "Next Action" card (falls back on failure)    │
  │  - Discovered Project Detail's Recent Activity              │
  │    (via a new project_id filter on /workspace/activity)     │
  │                                                              │
  │  Not yet wired (Sprint C2): Home's Today's Focus/Workspace   │
  │  Overview, Projects list, Advisor list                        │
  └────────────────────────────────────────────────────────────┘
```

`ProjectContext` is a composition layer, not a fifth persisted "project"
concept. It owns no table and no identity scheme of its own — it resolves
whichever identity it's given (a Workspace item id, a canonical/PI project
id, or both) via the exact same functions those two domains already use,
then assembles the result. See `docs/product/DECISIONS.md`'s new entry
("ProjectContext (Sprint C1) is a thin composition layer over existing
services, not a fifth 'project' concept") for the full reasoning.

## 2. Files created

```
dashboard/app/project_context/__init__.py
dashboard/app/project_context/models.py        # ProjectContext, AdvisorSummaryItem (Pydantic)
dashboard/app/project_context/builder.py        # build_project_context, build_project_contexts_for_workspace
dashboard/app/routers/project_context.py        # GET /project-context, GET /project-context/{id}
dashboard/tests/test_project_context_builder.py # 11 tests
dashboard/tests/test_project_context_api.py     # 6 tests
dashboard/tests/test_project_context_ui.py      # 3 tests
docs/architecture/14_PROJECT_CONTEXT_SPRINT_C1_REPORT.md  # this file
```

## 3. Files modified

```
dashboard/app/main.py                # + project_context router registration
dashboard/app/workspace/service.py   # enrich_project_item: + optional ai_summary param,
                                      #   + ai_sessions key in its return value (real bug fix,
                                      #   see §5); get_enriched_item: dedupe the double
                                      #   get_ai_session_summary call; list_project_assets/
                                      #   list_activity_feed: + optional project_id filter
dashboard/app/routers/workspace.py   # /assets, /activity: pass project_id through server-side
dashboard/app/static/js/app.js       # renderCockpitPage: + best-effort /project-context fetch
                                      #   for Next Action; renderDiscoveredProjectDetail: Recent
                                      #   Activity now calls /workspace/activity?project_id=
                                      #   instead of fetching everything and filtering client-side
dashboard/tests/test_workspace_sprint4_api.py  # +2 tests (latest_ai_session fix, activity
                                      #   project_id scoping)
dashboard/tests/test_workspace_service.py      # +2 tests (ai_sessions key present, exactly-once
                                      #   AI-session lookup)
CHANGELOG.md, docs/product/DECISIONS.md, dashboard/README.md,
docs/architecture/07_ROADMAP.md, docs/architecture/08_IMPORT_ENGINE_PROPOSAL.md
```

No file inside `app/discovery/`, `app/advisor/` (Epic 2's engine), or any
`app.projects.db`/`app.workspace.identity` public function's *signature*
was rewritten — `enrich_project_item` gained one optional keyword
argument (backward compatible; every existing call site is unaffected)
and one new key in its return dict (also backward compatible, since
`WorkspaceItem`'s Pydantic model already used `extra="allow"` — the same
mechanism that already let `next_action`/`documentation_status`/etc.
through in earlier sprints without being declared fields).

## 4. What duplicated logic disappeared

| Duplication (from the pre-sprint audit) | Resolution this sprint |
|---|---|
| `get_home_portfolio`'s `latest_ai_session` loop read `item.get("ai_sessions")`, a key `enrich_project_item` never set — silently always `None` | `enrich_project_item` now attaches the `ai_sessions` summary it already computes; the pre-existing loop in `get_home_portfolio` needed no changes at all to start working correctly |
| `get_enriched_item` called `get_ai_session_summary` twice per request (once inside `enrich_project_item`, again directly afterward) | `enrich_project_item` now accepts a precomputed `ai_summary`; `get_enriched_item` computes it once and passes it through — verified by a call-count regression test |
| Discovered Project Detail's Recent Activity fetched the *entire* activity feed (every adopted project's git/filesystem/asset work) and filtered client-side for one project | `/workspace/activity` and `/workspace/assets` both gained a server-side `project_id` filter that restricts the underlying computation, not just the returned rows |
| Cockpit's "Next Action" was computed ad hoc from only the current session's snapshot, with no fallback to git/filesystem heuristics (unlike Workspace's `extract_next_action`, which already checks `NEXT_ACTION.md`/`TODO.md`/`ROADMAP.md`/README/CHANGELOG/git commit) | Cockpit now consults `/project-context/{id}`'s `next_action` first (best-effort, falls back to its old computation on any failure) — a project linked to a discovered folder shows the same richer answer in both Cockpit and the Workspace-side detail view |
| Two structurally different recommendation shapes (Epic 2's `priority_score`/`confidence_score`/`title`/`suggested_action` vs. Workspace Advisor's `priority`/`confidence`/`recommendation`) forced any future consumer to know which engine it was talking to | `ProjectContext.advisor_summary` normalizes both into one shape (`title`/`reason`/`evidence`/`priority`/`confidence`/`action_link`/`source`) — neither underlying engine changed; only the new consolidated surface merges their output |
| A purely-manual Project's "next action" had no equivalent to Workspace's multi-source extraction at all | The builder's manual-project fallback (snapshot's `next_prompt`, tagged `source: "ai_session"`) gives every project *some* `next_action` value with a known provenance, closing that specific gap for the one new consumer (Cockpit) that reads it |

Deliberately **not** touched this sprint (see §7): the four underlying
"what is a project" concepts identified by the pre-sprint audit
(`app.projects` PI Projects, `app.workspace` Discovery/Adoption, Epic 2
Advisor, Workspace Advisor 2.0) still exist as four separate code paths —
`ProjectContext` reads from all four, it does not merge or replace any of
them. `/workspace/adopted` (`list_adopted_as_projects`) — flagged by the
audit as an apparently-unused, less-complete duplicate of
`/workspace/discovered?view=top_level` — was **not removed**: it has its
own existing, passing test coverage (`test_workspace_api.py`,
`test_workspace_service.py`) and is a public, documented endpoint from
Sprint 2/4. Deleting a tested public API is exactly the kind of
regression this sprint's "backward compatibility preserved" success
criterion prohibits; it's left alone, flagged as a Sprint C2 deprecation
candidate instead of removed unilaterally.

## 5. Two real bugs fixed while centralizing

Not rewrites — the same functions, wired correctly instead of
inconsistently:

1. **`get_home_portfolio`'s `latest_ai_session` was silently always
   `None`.** Its loop read `item.get("ai_sessions")`, but
   `enrich_project_item` (which builds `item`) never set that key — only
   the single-item `get_enriched_item` path did. Home's "Latest AI
   Session" card showed "Not yet defined" even when a real, current
   session existed. Verified fixed both by a new pytest regression test
   and live in a browser against the real workspace (see §8).
2. **`get_enriched_item` queried the same AI session summary twice.**
   Once inside `enrich_project_item`, once again directly afterward to
   set `enriched["ai_sessions"]`. `enrich_project_item` now accepts a
   precomputed `ai_summary` parameter; `get_enriched_item` computes it
   once and passes it through. Verified by a monkeypatch call-count test
   asserting exactly one `list_ai_sessions` call per `get_enriched_item`
   invocation.

## 6. Tests

- **Builder unit tests** (`test_project_context_builder.py`, 11): returns
  `None` when neither identity resolves; resolution by item id, by
  canonical project id, and both agreeing; a purely-manual project
  resolving correctly with an empty `git`/`resume_state.available=False`;
  the manual-project next-action fallback vs. a discovered project's
  `extract_next_action` precedence (both directions explicitly asserted,
  not just one); health-tier bucketing at every boundary; advisor-summary
  shape normalization; the knowledge-count soft cross-reference never
  raising even with no knowledge database configured; the bulk variant
  agreeing with the single-item variant on identity while skipping the
  expensive per-item fields; the bulk variant excluding unadopted items
  by default.
- **API integration** (`test_project_context_api.py`, 6): 404 for an
  unknown identifier; item-id and canonical-project-id lookups agreeing;
  the bulk endpoint excluding unadopted items; Resume Work then the
  context reflecting the real session/timeline; a purely-manual PI
  project resolving through the same endpoint; a full before/after
  filesystem snapshot proving no scanned project file is ever modified.
- **Frontend regression** (`test_project_context_ui.py`, 3): the
  Discovered Project Detail page's Recent Activity section uses the new
  server-scoped `project_id` fetch and no longer contains the old
  client-side `.filter((e) => e.project_id ...)` call; Cockpit's render
  function references `/project-context/` and `context.next_action`; the
  new router responds.
- **Regression additions** to existing suites
  (`test_workspace_sprint4_api.py`, `test_workspace_service.py`, 4 tests
  total): `latest_ai_session` is real (not `None`) after a real session
  exists; `/workspace/activity?project_id=` returns only that project's
  events while the unscoped call still returns all of them;
  `get_enriched_item` triggers exactly one `list_ai_sessions` call;
  `enrich_project_item`'s output carries the `ai_sessions` key.
- **Full suite: 926 passed, 0 failed** (up from 902 before this sprint —
  24 new tests: 11 + 6 + 3 + 4). `ruff check --fix` and `black` run on
  every new/touched file (the pre-existing `B008` `Depends`/`Body`-in-
  argument-defaults findings in `workspace.py`'s untouched lines, and two
  new, deliberate `BLE001` blind-exception catches around the
  knowledge-count and Epic 2 advisor calls — both documented soft-failure
  boundaries, consistent with this codebase's established pattern for
  optional cross-references — were left as intentional). `node --check
  app.js` clean.

### Real-workspace verification

Ran against the real `1 - IA PROJECTS` folder via a freshly started
server:

- `GET /project-context` (bulk) and `GET /project-context/{id}` (both by
  item id and by canonical project id) returned 200 with real field
  values for all five real adopted projects.
- Opened the Workspace page and the Discovered Project Detail view for
  `ROLE_OS` live in a browser: Recent Activity rendered real events
  (AI session, snapshot, filesystem changes, adoption, git commits), and
  the network panel confirmed the request was
  `GET /workspace/activity?project_id=60ae784ee6c67df0` (server-scoped),
  not the old whole-feed-then-filter call.
- Opened Cockpit for both a purely-manual project and `ROLE_OS`
  (canonical-linked): both loads issued a `GET /project-context/{id}`
  request (200 in both cases) before rendering; no console errors beyond
  unrelated Chrome-extension messaging noise.
- Opened Home: "Latest AI Session" — previously always blank — now shows
  the real current session title, live confirmation of the §5 bug fix.
- No scanned project file was modified at any point (also covered by an
  automated before/after filesystem snapshot test).

## 7. Performance impact

- **Net reduction** in per-request work for the two paths this sprint
  touched: `get_enriched_item` now performs one fewer `list_ai_sessions`
  query per call; the Discovered Project Detail page's Recent Activity
  now walks only the requested project's git/filesystem/assets instead
  of every adopted project's.
- **Net addition, bounded**: `build_project_context` (single-item path)
  calls the Epic 2 advisor engine (`refresh_recommendations` + a DB read)
  in addition to the Workspace Advisor rules already computed by
  `enrich_project_item` — a real, additional cost per single-project
  fetch, deliberately *not* incurred by the bulk variant (`include_epic2_
  recs=False`), which a list page would otherwise pay once per row.
  Cockpit's added `/project-context/{id}` fetch is one extra HTTP round
  trip per Cockpit page load, wrapped in try/catch so a slow or failing
  call never blocks the page (it only delays the Next Action card's
  final value, which starts from the same fallback it always had).
- **No change** to Discovery Engine scan cost, Workspace rescan cost, or
  any endpoint's existing query pattern beyond the two explicitly listed
  above.

## 8. Technical debt removed

- The always-`None` `latest_ai_session` dead code path in
  `get_home_portfolio` (real bug, now fixed, now covered by a regression
  test that would fail if it recurred).
- The duplicate AI-session query in `get_enriched_item` (now covered by
  an explicit call-count regression test).
- The Discovered Project Detail page's O(all-adopted-projects) client-
  side activity filter (now a real server-side query).
- Cockpit's Next-Action computation having zero awareness of a linked
  discovered project's richer, multi-source Discovery Engine extraction
  (now consulted, with a safe fallback).

## 9. Known limitations / explicitly deferred

- **Home's "Today's Focus"/"Workspace Overview" sections, the Projects
  list page, and the Advisor list page are not yet rewired to
  `ProjectContext`.** The bulk endpoint (`build_project_contexts_for_
  workspace`) exists, is tested, and is ready — but Home's top sections
  are still 100% PI-Project-based (`/pi/projects` + `/advisor/
  recommendations`) while its "Your Projects" section is 100% Workspace-
  based (`/workspace/home`); they remain two disjoint universes on the
  same page this sprint did not merge. Rewiring five list-rendering call
  sites in one sprint, under a "no UI regression" success criterion, was
  judged too large a blast radius versus the two single-project detail
  views (Cockpit, Discovered Project Detail) this sprint did complete.
- **Epic 2's Advisor and Workspace Advisor 2.0 remain two separate rule
  engines.** `ProjectContext.advisor_summary` normalizes their *output
  shape* into one, but does not merge their *reasoning* — a project could
  still receive contradictory-sounding recommendations from each engine.
  Deciding whether these should become one engine (not just one output
  shape) is a product question, not something this sprint's "do not
  rewrite Advisor" instruction permitted deciding unilaterally.
- **`/workspace/adopted` was left in place**, still duplicating (a less-
  complete version of) `/workspace/discovered?view=top_level`, because it
  has existing test coverage and is a documented public endpoint —
  removing it was judged out of scope for a sprint whose explicit success
  criterion is backward compatibility, not endpoint minimization.
- **The `knowledge_count` field is a soft, name-based cross-reference**
  (case-insensitive exact match against `knowledge_cards.project`, a
  free-text field with no real identity link to PI/Workspace/canonical
  ids) — it can under- or over-count for a project whose display name
  doesn't exactly match how it was referenced in an imported
  conversation. This is inherent to that domain's existing identity
  scheme, not something this sprint could fix without rewriting the
  Knowledge/Conversation Importer domain (explicitly out of scope).
- **`resume_state.available` reflects Workspace's adoption gate
  specifically** (whether Resume Work has been made available for a
  *discovered* item), not whether Cockpit's own, separate, pre-existing
  Resume Work mechanism would work for a purely-manual project (it always
  does, unconditionally, since Sprint 5). A caller reading `resume_state`
  for a manual project should not interpret `available: false` as "Resume
  Work is broken here" — it means "there is no Workspace item to resume
  through," which is a different, narrower claim.

## 10. Recommended Sprint C2

1. Rewire Home's "Your Projects"/"Today's Focus"/"Workspace Overview"
   sections, the Projects list page, and the Advisor list page to
   `build_project_contexts_for_workspace()` — collapsing Home's two
   disjoint project universes into one, and retiring whichever of
   `/pi/projects`+`/advisor/recommendations` vs. `/workspace/home`+
   `/workspace/advisor` calls duplicate what the bulk context now
   provides more completely.
2. Decide whether Epic 2's Advisor and Workspace Advisor 2.0 should
   become one rule engine reasoning over the unified `ProjectContext`
   object, rather than two engines whose output this sprint only
   normalizes at the edge.
3. Revisit `/workspace/adopted` once C2's list-page rewiring is done —
   if nothing still depends on its distinct (incomplete) shape, deprecate
   and remove it then, with its own dedicated migration/removal sprint
   rather than an incidental deletion.
