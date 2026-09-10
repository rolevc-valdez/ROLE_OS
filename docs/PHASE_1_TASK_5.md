# Role OS 2.0 — Phase 1 Task 5

## Objective

Role OS must never silently present stale, fallback, snapshot, or degraded information as though it were current/live. Reuse existing backend truth; make it visible in Mission Control without turning it into a diagnostics screen.

## Existing Freshness Signals

Traced across every module named in the brief (Step 1):

| Signal | Origin | Meaning | In Mission Control payload? | Rendered in UI before Task 5? |
|---|---|---|---|---|
| `data_freshness` (`last_scan`, `hours_since_scan`, `stale_threshold_hours`, `is_stale`) | `app/workspace/service.py: get_freshness()` | Discovery scan age | Yes, top-level, always | Yes — `renderDashFreshnessBanner()`, page-level banner |
| Executive Decision `confidence` discount | `app/executive_decision/scoring.py` (`_STALE_DATA_CONFIDENCE_PENALTY`), fed by `is_data_stale = get_freshness().get("is_stale")` in `service.py` | Confidence is *discounted, never the score itself*, when Discovery data is stale (per `docs/product/DECISIONS.md`) | Yes, via `executive_decision.confidence` and an evidence string (`"data_freshness.is_stale = true -- confidence discounted accordingly"`) | Confidence % badge: yes. The evidence string explaining *why*: buried at the bottom of a bullet list, easy to miss |
| `rule_discovery_scan_stale` / `rule_knowledge_stale` | `app/operational_intelligence/rules.py` | Staleness surfaced as its own recommendation, competing for a slot in Today's Focus/Needs Attention | Yes, if it ranks high enough | Yes, if it appears (unchanged, ranking not touched) |
| `snapshot_continuity` / `latest_snapshot` | `app/project_memory/service.py` via `project_context`, surfaced by `mission_control/service.py: _snapshot_continuity()` | A human-authored save of project state — historical by definition, never live | Yes | Yes, but labeled only "Latest Snapshot" — not explicitly marked as historical/point-in-time |
| `read_recent_decisions()`'s `source`/`note` | `app/session/decisions_adapter.py` | `"ecosystem"` (live read) vs `"fallback"` (frozen 2026-07-30 snapshot) when the external ecosystem decision log isn't configured/reachable — **the exact Phase 0 audit finding** | **No — not composed into Mission Control at all before this task** | **No — not rendered anywhere in the UI before this task** (only reachable via `GET /session/recent-decisions`, which no frontend code called) |
| `database_connected` | `app/routers/health.py` via `database_exists()` | Whether the Knowledge DB file is present | No (health-only) | Yes, on `/health` only — out of Mission Control's scope, unchanged |

## Existing Fallback Behavior

`decisions_adapter.read_recent_decisions()` already does exactly the right thing at the data layer: it never crashes, never guesses a path, and always returns a small, explicitly-labeled snapshot with `source: "fallback"` and a human-readable `note` explaining why, whenever `ROLE_OS_ECOSYSTEM_DECISION_LOG_PATH` is unset, missing, unreadable, or empty. This module needed **zero logic changes** — the honesty already existed. The problem was purely visibility: nothing in the application ever rendered `source` or `note` anywhere.

## Visibility Problem

Two concrete gaps found:
1. The Phase 0 audit's flagged risk — ecosystem decisions fallback — had a computed `source`/`note` with no consumer anywhere in the UI, and wasn't even part of Mission Control's payload.
2. Executive Decision's stale-data confidence discount was technically visible (a lower % badge, a bullet in a list) but not *distinguishable at a glance* — the brief's explicit bar ("MUST NOT present the recommendation as indistinguishable from a current recommendation") wasn't met by a quieter confidence number alone.

## Implemented Presentation Model

No new persistence, no new module. Five presentation-level states, each derived from existing fields already described above:

- **CURRENT** — `data_freshness.is_stale === false` and `ecosystem_decisions.source !== "fallback"`. No warning rendered (Step 3's explicit rule).
- **STALE** — `data_freshness.is_stale === true`. Rendered two ways, both pre-existing except the new inline note: the page-level banner (`renderDashFreshnessBanner`, unchanged) and a new inline note on the Executive Decision card (`mcStalenessNoteHtml`, new — see below).
- **FALLBACK** — `ecosystem_decisions.source === "fallback"`. Rendered by the new `mcEcosystemDecisionsHtml()` as a `Fallback snapshot` badge plus the adapter's own `note` text.
- **HISTORICAL / SNAPSHOT** — `snapshot_continuity.has_snapshot === true`. Existing card, relabeled "Saved Snapshot" with a `historical` badge (was "Latest Snapshot" with no qualifier).
- **UNAVAILABLE** — no scan ever recorded (`hours_since_scan === null`) or no recommendation available (`primary_focus.available === false` / `executive_decision.recommended_project === null`). All three cases already had honest, non-crashing messages; unchanged.

## Mission Control Changes

`dashboard/app/static/js/app.js`:
- New `mcStalenessNoteHtml(freshness)` — a short inline note ("⚠ Based on workspace data last scanned Xh ago — this recommendation's confidence is already discounted for that") rendered inside the Executive Decision card only when `data_freshness.is_stale`; empty string otherwise.
- `mcExecutiveDecisionHtml(decision, freshness)` — now takes `freshness` as a second argument and renders the note above; the call site now passes `data.data_freshness`.
- New `mcEcosystemDecisionsHtml(ed)` — renders the (new) `ecosystem_decisions` field: a `Live`/`Fallback snapshot` badge, the decision list, and (only when fallback) the adapter's own note text as a visible warning line.
- `mcSnapshotContinuityHtml()` — relabeled "Latest Snapshot" → "Saved Snapshot" with an explicit `historical` badge; the timestamp line now reads "Saved {date}" instead of a bare date.
- New mount point `mc-ecosystem-decisions`, placed inside the existing "What Matters Now" section, directly below the Executive Decision card.

No mount point was removed, no existing composer function's *content* logic changed (only their inputs/labels), and Portfolio Ranking / Today's Focus / ordering from Task 4 is untouched.

## Executive Decision Fallback

Reproduces the Phase 0 risk directly (Step 11): with `ROLE_OS_ECOSYSTEM_DECISION_LOG_PATH` unset (the default on any machine that hasn't configured it — **which is this machine's actual current state**, confirmed live in Step 12 below), `build_mission_control()`'s new `ecosystem_decisions` field reports `source: "fallback"` with the adapter's own note, while `primary_focus` and `executive_decision` remain fully populated and usable — the fallback is scoped to its own field and never blocks or degrades the rest of the payload. The UI renders a `Fallback snapshot` badge and the note text; a live-configured log (tested separately) renders a `Live` badge with no warning.

## Snapshot / Historical State

`snapshot_continuity`'s card now reads "Saved Snapshot `historical`" instead of "Latest Snapshot", and "Saved {date}" instead of a bare date — makes explicit that this is a point-in-time save, never confused with the adjacent "Last Activity" (live, git-derived) field.

## Unavailable State

Unchanged, already honest: "No projects tracked yet." / "No project currently has both a clear next action and enough evidence to recommend" / "No recommendation yet" — all pre-existing, all verified still present.

## Tests

New file `dashboard/tests/test_mission_control_freshness_ui.py` (11 tests):
1. All pre-Task-5 payload keys still present (API compatibility, Step 9)
2. `ecosystem_decisions` is present as a new additive field with `source`/`decisions`/`note`
3. **The Step 11 acceptance test**: log path unset → `source: "fallback"`, decisions still usable, rest of the payload unaffected
4. A live-configured log → `source: "ecosystem"`, real parsed content
5. `mcEcosystemDecisionsHtml` renders a distinct fallback badge, only shows the warning note when fallback
6. `mcStalenessNoteHtml` exists, returns "" when not stale, and is wired into the Executive Decision card via `freshness`
7. CURRENT state renders no warning from either new helper
8. Snapshot Continuity is now visually distinguishable ("Saved Snapshot" + `historical` badge)
9. Unavailable state has safe messages, not a crash
10. Resume Work CTA and its wiring are unbroken
11. No sample/`role_os_alpha` dependency introduced

Regression slice (`mission_control`, `decisions_adapter`, `session`, `workspace`, `resume`, `project_memory`, `project_context` keyword match): see completion report for exact totals.

## Canonical Runtime Validation

Started the real app from `dashboard/` (real launcher CWD) against the canonical, migrated runtime data (Task 3D's 5 real adopted projects):
- `GET /` → `200`
- `GET /mission-control` → `200`
- `data_freshness`: `{"last_scan": "2026-09-10T15:00:03Z", "hours_since_scan": 3.4, "is_stale": false}` — current, no staleness note rendered (correct — Task 3D's own rescan kept this fresh)
- `ecosystem_decisions.source`: **`"fallback"`** — this machine genuinely has no `ROLE_OS_ECOSYSTEM_DECISION_LOG_PATH` configured, so the new fallback badge/warning is live and real right now, not just a test scenario
- `executive_decision.confidence`: `0.85` (full, undiscounted — consistent with `is_stale: false`)

No canonical data was touched: `role_os_workspace.db` (5 `adopted_projects`) and `role_os_session.db` (7 `registry_projects`) mtimes verified unchanged before/after. Only the shared asset cache grew further (pre-existing, already-documented behavior from the request-scoped filesystem walk).

## Files Changed

- `dashboard/app/mission_control/service.py` — new `ecosystem_decisions` field (additive), new import, docstring update
- `dashboard/app/static/js/app.js` — `mcStalenessNoteHtml` (new), `mcEcosystemDecisionsHtml` (new), `mcExecutiveDecisionHtml` (new `freshness` param), `mcSnapshotContinuityHtml` (relabeled), skeleton mount point + population call
- `dashboard/tests/test_mission_control_freshness_ui.py` — new, 11 tests

## Known Limitations

- The ecosystem-decisions fallback badge appears inside "What Matters Now" even though it's conceptually a separate (Session-page) domain — judged the right place per the brief's explicit framing of this exact risk under that heading, and because Mission Control is now the one screen most likely to be seen; the Session page itself still has no direct UI for this data either (out of scope — Task 5 targets Mission Control specifically).
- No global "materially degraded" banner was added beyond the existing per-section signals (Step 7 preference for section-level warnks over a scary global one) — with only one optional, non-critical source (ecosystem decisions) ever falling back in current testing, a global banner was judged unnecessary and likely to overwarn.

## Exact Next Task

Phase 1 — Task 6: Legacy Dashboard Preservation
