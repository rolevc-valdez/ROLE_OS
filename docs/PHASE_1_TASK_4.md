# Role OS 2.0 — Phase 1 Task 4

## Objective

Make Mission Control the canonical Role OS landing experience, answering "Where did I leave off? / What matters now? / What's next?" immediately, with a prominent Continue Working / Resume Work action — by composing existing backend intelligence, not building new intelligence.

## Previous Mission Control Experience

Inspection (Step 1) found Mission Control was already far more built than the task brief assumed:

- `GET /mission-control` (`dashboard/app/routers/mission_control.py` → `app/mission_control/service.py: build_mission_control()`) already composes Project Context, Operational Intelligence, Executive Decision, Home's portfolio ranking, Daily Session, and Snapshot Continuity into one payload — exactly the "composition layer, not new intelligence" the brief asks for. No backend gap existed.
- `/` already renders `dashboard/app/templates/index.html`, a single-page shell whose client-side router (`dashboard/app/static/js/app.js`) defaults the empty hash to `"home"`, and `routes["home"] = renderMissionControlPage` — meaning **`/` has rendered Mission Control by default since Sprint C5** (comment in `app.js`: "Mission Control is now the primary Home experience"). The sidebar's first nav item is already labeled "Mission Control" and marked active by default.
- `renderMissionControlPage()` already rendered: an Executive Decision "TODAY" card, a Portfolio Ranking grid, a "Continue Working On" Primary Focus card (project, status, next action, latest snapshot, latest AI session, last activity, reasons, and a **"Resume Work →"** button wired to the real `resume-work` endpoint), Today's Focus, Since Last Time, Needs Attention, Recent Activity, Daily Session, Value Signal, Quick Actions, and a Portfolio strip.
- `triggerResumeWork()` already correctly called `POST /workspace/discovered/{item_id}/resume-work` and branched on `execution_target` (`claude_code`, `user_choice`, web assistant), `requires_user_objective`, and `context_sufficient` — the full, correct `workspace/resume.py`/`workspace/execution_target.py` behavior, with no parallel implementation.

**What was actually missing**: the *visual hierarchy*. The page opened with the Executive Decision card, then immediately a Portfolio Ranking analytics grid (all adopted projects, ranked, scored) — before the "Continue Working On" / Resume Work card ever appeared. This buries "Where I Left Off" and the primary CTA below an analytics view, which is the opposite of the brief's explicit "advanced analytics must not dominate the first screen."

## New Landing Experience

Reordered `renderMissionControlPage()`'s HTML skeleton only (`dashboard/app/static/js/app.js`) — no new render function, no new fetch, no backend change:

1. Mission Control title + freshness banner (unchanged)
2. **"Where I Left Off"** — wraps the existing Primary Focus + Snapshot Continuity card (unchanged content)
3. **"What Matters Now"** — wraps the existing Executive Decision "TODAY" card (unchanged content)
4. **"What's Next"** — wraps the existing Today's Focus grid (unchanged content)
5. Portfolio Ranking — moved here, now clearly secondary
6. Everything else, unchanged (Since Last Time / Needs Attention / Recent Activity / Daily Session / Value Signal / Quick Actions / Portfolio strip)

Every `id`-addressed mount point and every `mc*Html()` composer function is untouched; only the surrounding template-literal markup (headings, div order) changed.

## Where I Left Off

**Implemented:** reuses `data.primary_focus` (`home.suggested_project` + its `project_context`) and `data.snapshot_continuity` — `mcPrimaryFocusHtml()`/`mcSnapshotContinuityHtml()`, unchanged. Shows the recommended project, status, next action, latest human-authored snapshot (or an honest "not yet defined"), latest AI session, and last activity timestamp. Empty state ("Nothing to recommend yet" / "No projects tracked yet") is the existing, already-honest fallback — no fabricated state.

## What Matters Now

**Implemented:** reuses `data.executive_decision` (the Executive Decision Engine's single deterministic recommendation) — `mcExecutiveDecisionHtml()`, unchanged. Shows the one recommended project, its reason, expected benefit, decision score, and confidence. Empty state ("No recommendation yet") is existing and honest.

## What's Next

**Implemented:** reuses `data.todays_focus` (top 3 deduped Operational Intelligence recommendations) — `mcFocusItemCardHtml()`, unchanged, no new ranking. Empty state ("Nothing needs your attention today") is existing.

## Resume Work

**Implemented, unchanged.** The CTA is the existing `Resume Work →` button inside the "Where I Left Off" card, `btn btn-primary` (already visually prominent), disabled — not hidden or broken — when no resumable target exists. Backend reused verbatim: `POST /workspace/discovered/{item_id}/resume-work` → `app/workspace/resume.py: resume_work()` → `app/workspace/execution_target.py: classify_execution_target()`. Client-side `triggerResumeWork()` branches on the real response (`claude_code` → launch + navigate to Cockpit; `user_choice` → prompt; else → open web assistant), and surfaces the no-action/context-insufficient guards. No parallel resume mechanism was written.

## Canonical Landing Route

**Option A** (already in place, confirmed not re-implemented): `/` renders Mission Control directly via the existing SPA default route — no redirect, no duplicate implementation. `/mission-control` continues to serve the raw JSON payload the page's own JavaScript fetches, unchanged; a normal user only ever needs to visit `/`.

## Files Changed

- `dashboard/app/static/js/app.js` — `renderMissionControlPage()`'s HTML skeleton reordered and re-headed (no logic changes)
- `dashboard/tests/test_mission_control_landing_ui.py` — new, 7 tests

No Python backend file was modified.

## Tests

New file `dashboard/tests/test_mission_control_landing_ui.py` (7 tests, following this repo's established string-assertion convention for frontend regressions — no JS runtime/browser harness exists here):
1. `/` serves the app shell whose router defaults to Mission Control
2. `/mission-control` still loads
3. "Where I Left Off" appears before "What Matters Now" before "What's Next" before "Portfolio Ranking" in the rendered skeleton
4. "What Matters Now" wraps the existing Executive Decision mount point
5. The Resume Work CTA is present and wired to the existing `resume-work` endpoint/execution-target branches
6. Missing-state empty states are the existing honest ones, not fabricated
7. No sample/demo (`samples/role_os_sample`, `role_os_alpha`) reference was introduced

Regression slice run: `mission_control`, `workspace`, `project_memory`, `project_context`, `resume`, `execution_target`, `dashboard_ui`, `sprint5_ui` keyword match — **392 passed, 0 failed** (plus the 7 new tests, run separately: 7 passed).

## Known Limitations

- The Executive Decision card ("What Matters Now") still shows its full evidence list and score/confidence badge — judged acceptable rather than trimmed, since ROLE OS's core design principle is "never invent hidden weighting, document every contribution"; hiding evidence would work against that, not just simplify the page.
- "What's Next" (Today's Focus) and "Where I Left Off"'s own Next Action field can occasionally name different top items, since they come from two intentionally distinct existing rankings (Home's `suggested_project_to_continue` vs. the Operational Intelligence Engine's own sort) — this is pre-existing, documented architecture, not something Task 4 introduced or was asked to unify.
- The old "Command Center" Home view (`renderHome()`) remains in `app.js`, unused by any route (pre-existing since Sprint C5); left untouched per this task's "do not delete legacy routers" constraint.

## Deferred to Task 5

`data_freshness`, `is_stale`, and the existing `renderDashFreshnessBanner()` staleness banner are unchanged and still rendered at the top of the page — not hidden, not regressed, not expanded. Full staleness/fallback visibility (including surfacing `source`/`note` fields on fallback-capable data like the ecosystem decisions log) is Task 5's scope.

## Exact Next Task

Phase 1 — Task 5: Staleness / Fallback Visibility
