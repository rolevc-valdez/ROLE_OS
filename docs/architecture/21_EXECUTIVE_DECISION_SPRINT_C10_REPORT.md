# 21 — Executive Decision Engine, Sprint C10: Completion Report

Scope executed: build the Executive Decision Engine so ROLE OS stops
being an information dashboard and becomes a deterministic decision
system — one call answers "what should I work on next?" using evidence
from every existing domain (Project Context, Mission Control,
Operational Intelligence, Project Ecosystem, Impact Analysis, Project
Memory, Assets, Knowledge, Discovery, AI Sessions/Snapshots, Workspace).
No LLM, no embeddings, no AI API, no hidden weighting. No version bump,
no commit, no tag.

## Architecture

One new package, `app/executive_decision/`, following the same
"composition over a new source of truth" discipline every prior sprint
in this series established:

```
app/executive_decision/
    __init__.py  -- public entry point (get_executive_decision)
    models.py     -- canonical ExecutiveDecision/ranked-project/today-plan-step shapes
    scoring.py      -- compute_decision_score() -- fixed, additive, documented point table
    planner.py        -- build_today_plan() / estimate_effort_and_duration() / dependencies_status()
    service.py           -- get_executive_decision() -- the one public call, orchestrates everything
    api.py                 -- GET /executive-decision (inside the package, per C9's own convention)
```

No detector, no relationship type, no filesystem/knowledge scan exists
anywhere in this package. Every read is a call into an already-canonical
domain, or a direct import of an existing pure function (Project
Memory's own `_pending_work`/`_next_action_output`) rather than a
re-implementation of it.

## Files created

- `dashboard/app/executive_decision/__init__.py`
- `dashboard/app/executive_decision/models.py`
- `dashboard/app/executive_decision/scoring.py`
- `dashboard/app/executive_decision/planner.py`
- `dashboard/app/executive_decision/service.py`
- `dashboard/app/executive_decision/api.py` (`GET /executive-decision`)
- `dashboard/tests/test_executive_decision.py` (31 tests)

## Files modified

- `dashboard/app/main.py` — imported and registered the new
  `executive_decision.api` router.
- `dashboard/app/mission_control/service.py` — `build_mission_control()`
  gained `executive_decision`/`ranked_projects` fields, computed inside
  the existing `request_scope()` block (see "Real bugs found" below for
  why placement mattered).
- `dashboard/app/explorer/service.py` — new `_search_executive_decision`,
  wired into `search()`'s existing non-empty-query block; `RESULT_TYPES`
  gained `"Executive Decision"`.
- `dashboard/app/static/js/app.js` — two new render functions
  (`mcExecutiveDecisionHtml`, `mcPortfolioRankingHtml`) wired into
  `renderMissionControlPage`, now leading the page; `RESULT_TYPE_ORDER`
  and `EXPLORER_TYPE_ICONS` gained `"Executive Decision"` (plus the two
  pre-existing, previously-missing `"Ecosystem Relationship"`/`"Impact"`
  types — see "Real bugs found").
- `CHANGELOG.md`, `docs/product/DECISIONS.md`, `docs/product/
  CHANGELOG_PRODUCT.md`, `docs/architecture/07_ROADMAP.md`,
  `dashboard/README.md` — documentation.

## Decision model

`models.make_executive_decision` produces exactly the brief's suggested
fields: `generated_at, recommended_project, decision_score, confidence,
reason, expected_benefit, estimated_effort, estimated_duration,
blocking_projects, projects_unblocked, commercial_value, technical_value,
risk, dependencies, today_plan, expected_result, evidence, limitations`.
`risk` is asserted to be one of Impact Analysis's own five levels — this
engine never invents a second risk vocabulary, it reads Sprint C9's
`overall_risk` verbatim for the recommended project.

`ranked_projects` (returned alongside `decision` from
`get_executive_decision`, not embedded in the decision itself) is the
brief's "Project Priority" section: every adopted project, ranked, each
with `rank, project, decision_score, confidence, top_reasons` (the first
three evidence strings that produced its score).

## Scoring model

Nine contributors in `scoring.py`, each a pure function returning
`(points, reason | None)`:

| Contributor | Points | Reason string prefix |
|---|---|---|
| Operational Intelligence priority | `priority × 0.4` (max 40) | `"Operational Intelligence priority N/100"` |
| Business value | 10/20/25 (medium/high/critical) | `"business_value = X"` |
| Launch-ready bonus | +15 | `"Operational Intelligence: launch-ready"` |
| Projects unblocked | 5 each, capped at 15 | `"Unblocks N project(s): ..."` |
| Already blocking dependents | +10 | `"Already blocking N project(s) today: ..."` |
| Impact Analysis risk | 2/5/10/15 (low/medium/high/critical) | `"Impact Analysis: X risk ..."` |
| Pending work recorded | +5 | `"Project Memory: real pending work already recorded"` |
| Recent activity | +5 (≤3 days) | `"Active in the last N day(s)"` |
| Stale activity | -5 (≥30 days) | `"No activity in N day(s)"` |
| Project health | `health_score × 0.1` (max 10) | `"Project health score N/100"` |
| Paused/blocked status | -20 / -15 | `"Project status is 'X'"` |

`compute_decision_score()` sums every contributor's points (clamped
0-100) and appends every non-zero contributor's reason to `evidence`, in
this fixed order — a score is always reconstructable by re-reading the
function top to bottom. `confidence` is `0.85` when Operational
Intelligence produced a recommendation for the project, `0.5` otherwise,
discounted by `×0.85` (never dropped) when `workspace.get_freshness()`
reports stale data — with the discount itself named in `evidence`.

## Conflict resolution

`service._sort_key` sorts candidates by `(-decision_score, -health_score,
canonical_project_id)` — a three-part total order. The first two
criteria are real evidence (score, then health as a tiebreaker
reflecting "which project is the safer bet"); the third is a fixed,
arbitrary-but-stable identity comparison that can never itself produce a
tie. This is not a "pick the first one found" fallback — it's a total
order over every candidate, so the same input always produces the same
single winner, verified by `test_conflict_resolution_never_outputs_a_tie`
(two projects with identical evidence, called twice, same winner both
times).

## Today Plan

`planner.build_today_plan()` returns exactly one step for the
recommended project: `start_time` (a fixed `"09:00"` label, never a
real-clock computation), `action`, `project`, `objective`,
`expected_duration`, `expected_result`, `dependencies_status`,
`next_checkpoint` (a fixed `"Create Snapshot"`, matching the brief's own
worked example). `estimate_effort_and_duration()` is a static keyword
lookup over the action's own title/suggested-action text — the same
convention `operational_intelligence.models.expected_benefit_for`
already established — never a generated per-project estimate.
`dependencies_status()` reports `"Satisfied"` unless one of the
project's own dependencies (from the Ecosystem graph) is itself
blocked/at-risk, in which case it names which one.

## Project Priority (portfolio ranking)

Every adopted project competes: `get_executive_decision()` scores each
one via the same `_score_project()` function, then sorts them all with
the same `_sort_key`. `ranked_projects` is this full sorted list — no
project is scored differently depending on whether it happens to win.

## API

`GET /executive-decision` → `{"decision": ExecutiveDecision,
"ranked_projects": [...]}`. No query parameters — the brief asks for one
decision, not a filtered/paginated view.

## Mission Control integration

`build_mission_control()` calls `get_executive_decision()` once,
threading through the request's already-computed `all_contexts`/
`enriched_items`/`recommendations` — no second whole-workspace context
or Operational Intelligence pass. The frontend now leads with:

1. **"TODAY"** — `mcExecutiveDecisionHtml`: recommended project, score/
   confidence badge, reason, expected benefit, estimated effort/
   duration, next action, expected result, dependencies, evidence.
2. **"Portfolio Ranking"** — `mcPortfolioRankingHtml`: every adopted
   project, ranked, each with its own top 3 reasons.
3. Everything that used to lead the page (Primary Focus, Today's Focus,
   Since Last Time, Needs Attention, Value Signal, Portfolio strip) now
   renders below these two sections — supporting information, not the
   headline, per the brief's explicit instruction.

## Project Memory / Impact Analysis / Operational Intelligence: responsibility boundaries

Per the brief's explicit separation-of-concerns instructions:

- **Project Memory contributes context** (pending work, next action
  text) — Executive Decision imports its pure functions directly
  (`_pending_work`, `_next_action_output`) rather than re-deriving that
  logic, but the *decision* of what that context is worth (points,
  ranking) belongs entirely to `scoring.py`.
- **Impact Analysis contributes consequences** (`overall_risk`,
  evidence) — Executive Decision decides whether that risk level matters
  *today* by scoring it (2-15 points depending on level) alongside eight
  other contributors, never treating risk as an automatic disqualifier
  or an automatic winner.
- **Operational Intelligence contributes recommendations** (priority,
  suggested action, expected benefit) — when two projects each have their
  own top OI recommendation, Executive Decision resolves which one
  actually matters most today by scoring both fully (OI priority is only
  one of nine contributors) and picking the higher total, never simply
  the higher OI priority alone.

## Performance

Profiled directly against the real workspace:

| Stage | Time |
|---|---|
| `all_project_contexts()` | ~758ms |
| `get_operational_intelligence()` | ~75ms |
| `compute_relationships()` | ~571ms |
| `get_impact_analysis()` × 5 adopted projects | ~2ms |
| Project Memory pending-work reuse × 5 | ~0ms |

Executive Decision's **own** logic (scoring + ranking + planning, on top
of already-computed inputs) costs approximately 2ms. The end-to-end
`GET /executive-decision` request measured ~870ms-1.9s across several
live runs, entirely dominated by `all_project_contexts`/
`compute_relationships` — both pre-existing services whose costs on this
exact real workspace were already measured and documented in the C6
(`all_project_contexts`-adjacent work) and C8 reports. This sprint
introduces zero new filesystem or knowledge scans; every input is
computed at most once per request via the same "compute once, thread
through as an optional parameter" convention established in C7.1/C8/C9,
verified by a dedicated regression test
(`test_passthrough_all_contexts_reduces_whole_workspace_passes`).

**The brief's 500ms target is not met on this real, ~18-project
workspace** — reported honestly rather than redefined to appear met,
matching this project's established practice (the C8 report's own
"~1.1-1.4s" for a single ecosystem call).

## Security

Only adopted projects are ever scored or ranked
(`adopted_contexts = [c for c in all_contexts if c.get("is_adopted")]`) —
inherited unchanged from Project Ecosystem/Impact Analysis's own security
boundary. Verified by `test_unadopted_discovered_projects_never_compete`
(a discovered-but-not-adopted folder never appears in `ranked_projects`).

## Real bugs found and fixed

1. **Double filesystem walk from a `request_scope()` placement error.**
   The first Mission Control integration placed the new
   `get_executive_decision()` call immediately *after* Mission Control's
   existing `with request_scope():` block closed. Since Executive
   Decision's own `compute_relationships()` call triggers the Ecosystem
   Engine's shared-assets detector (a filesystem walk), and that walk was
   no longer covered by the shared cache scope, it re-walked the
   filesystem once per adopted project (5 times on the real workspace)
   instead of reusing the single walk `request_scope()` already
   collapsed everything else to. Caught immediately — before this ever
   reached a live server — by the pre-existing regression test
   `test_no_double_asset_walk_per_project_per_request` failing on the
   first full targeted-regression run. Fixed by moving the
   `get_operational_intelligence`/`get_executive_decision` calls inside
   the existing `request_scope()` block.
2. **A pre-existing, two-sprint-old dead result-type bug, found only by
   live browser verification.** Explorer's frontend maintains its own
   `RESULT_TYPE_ORDER` array (governing render order), separate from the
   backend's `RESULT_TYPES` tuple. This array was never updated when
   Sprint C8 added `"Ecosystem Relationship"` or Sprint C9 added
   `"Impact"` — both types have been present in every `GET
   /explorer/search` response (confirmed via `counts`) but silently
   un-renderable in the actual UI since those sprints shipped, because no
   existing test asserts against the *rendered* set of visible groups,
   only the API response shape. Live-verifying this sprint's own new
   `"Executive Decision"` type surfaced the same gap for it. Fixed by
   adding all three missing types to `RESULT_TYPE_ORDER` (and matching
   icons to `EXPLORER_TYPE_ICONS`) in one pass, rather than only the type
   this sprint introduced.
3. **A test that assumed a globally-empty workspace, found only by the
   full (not targeted) regression run.**
   `test_no_adopted_projects_returns_honest_empty_decision` called
   `get_executive_decision(settings=settings)` expecting zero adopted
   projects, relying on the `settings` fixture's fresh, tmp_path-scoped
   `Settings()`. But that fixture only overrides
   `ROLE_OS_PROJECTS_DB_PATH`/`ROLE_OS_ECOSYSTEM_DB_PATH` — the
   Workspace/Discovery overlay database (where "adopted" status lives)
   is a single, session-wide store not isolated by it, so by the time
   this test ran after ~30 other test files (each adopting their own
   synthetic projects against that same shared store) in one full-suite
   run, real adopted projects from earlier files were still present.
   Reproduced deterministically by running every file that precedes
   `test_executive_decision.py` alphabetically plus this one together;
   fixed by passing `all_contexts=[]`/`enriched_items=[]` directly to
   `get_executive_decision()` instead of relying on nothing being
   adopted anywhere in the shared session — the same passthrough
   mechanism this engine already supports for performance, now also used
   here for test isolation. Re-verified: the full 1175-test suite passes
   with this fix in place.

## Tests

- `dashboard/tests/test_executive_decision.py` — 31 tests: every scoring
  contributor in isolation (with combined-baseline variants for the two
  penalty contributors, so their magnitude is provable without hitting
  the score's 0-point floor), the effort/duration keyword lookup,
  `dependencies_status`, Today's Plan shape (single step, empty when no
  project), the `ExecutiveDecision` model's risk-level assertion, an
  honest empty decision with zero adopted projects, business-value-driven
  ranking, a paused project never beating an active one, ranked-projects
  sort order, conflict resolution (never a tie, deterministic across
  repeated calls), the adopted-only security boundary, Today's Plan
  presence on the winner, a performance-passthrough regression (fewer
  `all_project_contexts` calls with vs. without passthrough), the API's
  full field shape, Mission Control integration, and Explorer integration
  (including a regression proving an empty/browse query never triggers
  the engine).
- Full targeted regression (`test_executive_decision.py` +
  `test_mission_control_api.py` + `test_operational_intelligence.py` +
  `test_project_ecosystem.py` + `test_impact_analysis.py` +
  `test_project_memory.py` + `test_explorer_api.py` +
  `test_explorer_ui.py` + `test_explorer_v2.py` + `test_cockpit_ui.py` +
  `test_cockpit_redesign_ui.py`): **242 passed**, 0 failed.
- Full suite: **1175 passed**, 0 failed (run in 4 batches to fit the environment's execution-time limits; a real cross-file-state bug was found and fixed in the process -- see below).
- `ruff check` / `black --check`: clean on every file this sprint
  touched (fixed 4 `ISC004` implicit-string-concatenation findings in the
  new `_MAX_LIMITATIONS` list; the remaining `B008`/`BLE001` findings are
  the same pre-existing, repo-wide accepted patterns noted in the C8/C9
  reports, present in files this sprint did not touch).
- `node --check app/static/js/app.js`: passes.

## Live verification (real workspace)

Ran against `C:\Users\rolev\My Drive (rolevc@gmail.com)\1 - IA PROJECTS`
via the actual running application (restarted after every code change,
per this session's established discipline that Python does not
hot-reload):

- `GET /executive-decision` returned a full, real ranking of all 5
  required projects:

  | Rank | Project | Score | Top reasons |
  |---|---|---|---|
  | 1 | ROLE Commerce Factory | 71.6 | OI priority 70 ("Consider shipping/launching"); business_value=medium + launch-ready; Impact Analysis medium risk |
  | 2 | ROLE_OS | 58.9 | OI priority 65 ("Keep the momentum going"); business_value=medium; medium risk |
  | 3 | ROLE_KNOWLEDGE_OS | 53.8 | OI priority 60 ("Fix hardcoded paths/config before relocating"); business_value=medium; medium risk |
  | 4 | role-ecosystem | 51.5 | OI priority 65 ("Keep the momentum going"); business_value=medium; medium risk |
  | 5 | ROLE MASTER | 40.8 | OI priority 40 ("Continue: Confirm TYPOGRAPHY.md font choices and licensing"); business_value=medium; medium risk |

  ROLE Commerce Factory wins deterministically, on real evidence,
  matching the brief's own worked example almost exactly ("High
  commercial readiness, no blockers, highest operational benefit").
- Browser-verified: opened Mission Control (`#/mission-control`) and
  confirmed the "TODAY" card renders first (recommended project,
  score/confidence badge, reason, expected benefit, estimated effort
  "High"/duration "2-4 hours", next action, expected result,
  dependencies "Satisfied", evidence list), followed immediately by
  "Portfolio Ranking" (all 5 projects, ranked, each with its own top
  reasons), with the pre-existing operational cards below both.
- Browser-verified: opened Explorer (`#/explorer`), searched `"today"`,
  and confirmed a new "Executive Decision" result group renders at the
  top with the title `"Today's Decision: ROLE Commerce Factory (71.6
  pts)"` and the real evidence summary.
- No console errors from application code (one benign, pre-existing
  Chrome-extension messaging artifact unrelated to this app, also seen in
  every prior sprint's live verification).

## Known limitations

- **The 500ms performance target is not met on this real workspace.**
  Executive Decision's own logic costs ~2ms; the remainder is inherited,
  already-documented cost from `all_project_contexts`/
  `compute_relationships` (C6/C8). Meeting 500ms would require optimizing
  those pre-existing services, out of this sprint's scope ("consume
  existing domains only, no new discovery").
- **No scheduling engine or calendar integration**, by explicit brief
  instruction — Today's Plan is always exactly one step with a fixed
  `"09:00"` label.
- **Estimated effort/duration are a static per-keyword lookup**, not a
  per-project estimate — two very different projects whose top action
  happens to share a keyword (e.g. both titled "Continue...") get the
  same effort/duration text.
- **No manual override / acknowledge workflow** — unlike Project
  Ecosystem's relationships (dismiss/confirm), a decision cannot be
  annotated "I disagree, don't recommend this again today." Consistent
  with the brief's analysis/decision-only scope, worth naming as a gap.

## Recommendation for C11

1. **A lightweight "why not X" explainer** — for the #2-ranked project,
   surface specifically which contributor(s) would need to change for it
   to overtake #1 (e.g. "10 more health-score points would tie it"),
   turning the ranking from a report into actionable guidance for
   improving a project's own standing.
2. **Manual acknowledge/snooze** — a `POST /executive-decision/
   acknowledge` (or similar) letting a user say "seen, don't recommend
   this again today," the same override-without-mutating-evidence pattern
   Project Ecosystem's `role_os_ecosystem.db` already established for
   relationships.
3. **Investigate `all_project_contexts`/`compute_relationships` caching
   across requests within a short TTL** (e.g. 30-60s) specifically to
   bring Mission Control/Executive Decision under the 500ms target on
   real workspaces — carefully, since both already documented reasons
   they recompute fresh each time (data freshness guarantees), so any
   cache would need an explicit invalidation story, not just a blind TTL.
