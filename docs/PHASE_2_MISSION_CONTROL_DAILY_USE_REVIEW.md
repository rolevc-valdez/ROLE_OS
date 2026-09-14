# Role OS 2.0 — Mission Control Daily-Use Review

## Objective

Evaluate whether Mission Control (`GET /`, `GET /mission-control`) is genuinely useful as Role's daily control center — able to answer, quickly and without prior conversational context: where did I leave off, what matters now, what should I do next, and can I continue working immediately. This is an evaluation task, not an implementation mandate; "no change needed" is an acceptable, expected outcome per `docs/ROLE_OS_2_PHASE_2_PLAN.md` (Task 2.2).

## Current Experience

Traced end-to-end, code and live rendering both inspected (not just prior task reports):

- **Backend composition:** `dashboard/app/mission_control/service.py: build_mission_control()` — one `GET /mission-control` call, pure composition over existing services (`app.project_context.builder.all_project_contexts`, `app.workspace.service.get_home_portfolio`/`list_activity_feed`, `app.operational_intelligence.get_operational_intelligence`, `app.executive_decision.get_executive_decision`, `app.session.db`, `app.session.decisions_adapter`). No second ranking engine, one filesystem walk per request (`app.assets.service.request_scope()`).
- **API:** `dashboard/app/routers/mission_control.py` — one route, `GET /mission-control`, returns the already-shaped payload verbatim.
- **Frontend:** `dashboard/app/static/js/app.js: renderMissionControlPage()` (DOM built at line ~1308) — one fetch, no client-side joining/ranking/deduping (`mc*Html` functions only format already-shaped fields). Real page structure, top to bottom:
  1. `Mission Control` heading + freshness banner (`mc-freshness-banner`)
  2. **Where I Left Off** — Primary Focus card (`mcPrimaryFocusHtml`) + Snapshot Continuity
  3. **What Matters Now** — Executive Decision card (`mcExecutiveDecisionHtml`) + Recent Ecosystem Decisions
  4. **What's Next** — Today's Focus (`mcFocusItemCardHtml` × 3)
  5. Portfolio Ranking (all adopted projects, scored, analytics-style grid — intentionally placed *below* the three-question block per Phase 1 Task 4)
  6. Two-column: Since Last Time / Needs Attention / Recent Activity — Daily Session / Value Signal / Quick Actions
  7. Portfolio (a compact card-grid of every adopted project, links to Workspace)
- Verified live via a real running instance against canonical runtime data (`dashboard/`, no env overrides) — not sample/demo data, not assumed from prior reports.

## Four-Question Assessment

### A. Where did I leave off? — **CLEAR**
- **Data source:** `primary_focus.project_context` (`app.project_context.builder`), reusing `workspace.portfolio.suggested_project_to_continue` verbatim — no independent scoring.
- **UI element:** "Where I Left Off" card, first thing on the page, always visible without any click.
- **Clarity:** Project name, status, next action (with its evidence source labeled, e.g. "source: latest git commit"), latest snapshot, latest AI session, last activity, and an explicit "Recommended because" bullet list.
- **Actionability:** A single, clearly primary "Resume Work →" button sits directly under the answer.
- **Ambiguity:** None in presentation. (One real-world caveat under "Canonical Runtime Examples" below — the *content* can be stale, but the UI is honest about that, which is a different concern from clarity.)
- **Extra click required:** No.

### B. What matters now? — **CLEAR**
- **Data source:** `executive_decision` (`app.executive_decision.get_executive_decision`), the one canonical decision engine.
- **UI element:** "What Matters Now" → Executive Decision card, immediately below Where I Left Off (one scroll on a typical laptop viewport — see Friction Findings).
- **Clarity:** Project, decision score + confidence badge, a plain-English "Reason," "Expected Benefit," effort/duration estimate, a "Next Action" line, and an itemized "Evidence" list. A staleness note is inlined directly on the card when relevant (`mcStalenessNoteHtml`), not hidden in a separate banner only.
- **Actionability:** The recommended project and its top action are named explicitly; clicking the project name navigates to it.
- **Ambiguity:** The "Expected Result" field, in the real example captured, reused a raw historical commit-message string verbatim inside a templated sentence ("milestone: Phase 3 local provider pipeline validated (2026-08-21T12:30:17-07:00) moves to a checkpoint-able state") — grammatically odd, reads like a past event described as a future goal. Does not block understanding (the "Next Action" line above it, "Consider shipping/launching," is unambiguous), but is a real, minor wording rough edge. See Friction Findings.
- **Extra click required:** No.

### C. What should I do next? — **CLEAR**
- **Data source:** `todays_focus` (top 3 by priority, deduped one-per-project, from the same Operational Intelligence output Executive Decision and Needs Attention also read).
- **UI element:** "What's Next" — three focus cards, one scroll further down.
- **Clarity:** Each card names the project, the action, a one-line reason, expected benefit, priority, and confidence.
- **Ambiguity:** None found.
- **Extra click required:** No.

### D. Can I continue working immediately? — **CLEAR**
- **Data source:** `primary_focus.project_context.resume_state` (`app.workspace.resume`), same backend Phase 1 verified end-to-end; no parallel implementation.
- **UI element:** "Resume Work →" button on the Where-I-Left-Off card; `data-resume-work-item` wired in `wireMissionControlActions`.
- **Clarity/actionability:** The button is present and enabled whenever `resume_state.available` is true (verified true in the live example, even though no snapshot/AI session exists yet for that project — the fallback path constructs a full ready-to-use prompt, confirmed present in the real payload).
- **Extra click required:** One click (clicking "Resume Work" itself) — which is the intended action, not friction.

## Canonical Runtime Examples

Captured from a real running instance (`dashboard/`, no environment overrides, canonical `var/role_os_dashboard/` data — 5 adopted projects) via `GET /mission-control` and the rendered `GET /`:

- **Primary Focus:** ROLE_OS — status `active`, health `warning` (79/100), next action `"fix: anchor runtime data paths to role os root (2026-09-09T20:03:14-07:00)"` (source: `latest git commit`, confidence 0.3), no snapshot, no AI session recorded, last activity `2026-09-10T07:59 AM`. Reasons: "has a next action (source: latest git commit)", "active in the last 4 day(s)".
- **Saved/current state (Snapshot Continuity):** `available: true, has_snapshot: false` — "Create a snapshot before switching or ending the day."
- **Executive Decision:** ROLE Commerce Factory — decision score 71.7, confidence 0.72 (discounted from staleness), reason "Operational Intelligence priority 70/100 ('Consider shipping/launching'); business_value = medium; ...", expected benefit "Unlocks the commercial/launch value already sitting in this project," effort High, duration 2-4 hours.
- **Today's Focus:** (1) ROLE Commerce Factory — "Consider shipping/launching" (priority 70, 75% confidence); (2) ROLE_OS — "Keep the momentum going" (priority 65, 80% confidence); (3) role-ecosystem — "Commit or stash uncommitted changes" (priority 55, 100% confidence).
- **Resume Work:** `available: true`, `is_new_session_needed: true`, a full generated prompt (project summary, current objective, "where we left off," pending work, next action, operational recommendation, conversation context), `execution_target: user_choice`, `recommended_assistant: claude_code`.
- **Freshness:** `last_scan: 2026-09-10T15:00:03Z`, `hours_since_scan: 85.8`, `is_stale: true` — rendered live as an amber "Stale discovery data" banner at the top of the page and as an inline note on the Executive Decision card.
- **Fallback source:** `ecosystem_decisions.source: "fallback"`, rendered with a "Fallback snapshot" badge and an explanatory note ("ROLE_OS_ECOSYSTEM_DECISION_LOG_PATH is not set...").

No project state was modified to produce these examples — read-only `GET` requests only. Canonical database checksums verified identical before and after this review's live server session (see Runtime Safety).

## Multi-Root Discovery Impact

Verified both statically and live, against real canonical data:

- `app.project_context.builder.all_project_contexts` calls `service.list_enriched_top_level_projects(adopted_only=True, ...)` — Mission Control's entire pipeline (Home portfolio, Operational Intelligence, Executive Decision, the Portfolio strip and Portfolio Ranking) reasons **only over adopted projects**, never over the raw Discovery/Workspace scan cache directly.
- Live confirmation: this server run had `ROLE_OS_DISCOVERY_ROOTS` unset (single-root, unchanged default) and `total_projects_tracked: 5` — matching the exact canonical adopted-project count recorded throughout Phase 1 and Task 2.1. Newly-discoverable-but-unadopted projects from Task 2.1's validation (`role-content-factory`, `charcos-site`, etc.) do not appear anywhere in this payload, because they were never adopted in this canonical database.
- **Conclusion: Multi-Root Discovery has zero effect on Mission Control's output**, by construction — enabling it only widens what the Workspace *scan cache* contains; adoption remains the sole gate into everything Mission Control reads. Priority semantics (Operational Intelligence, Executive Decision scoring) are untouched — they operate over the same `list_enriched_top_level_projects(adopted_only=True)` list regardless of how many roots were scanned to produce the underlying cache.
- No project was adopted during this task.

## Friction Findings

| # | Finding | Classification |
|---|---|---|
| 1 | The "Where I Left Off" (Primary Focus) card is tall enough (project name, status, next action, snapshot, AI session, last activity, reasons, CTA — all substantive, none filler) that on a common laptop viewport (measured at both 1366×800 and with a 1920×1080 window, screenshots identical) it occupies the entire first screen, so "What Matters Now" and "What's Next" require scrolling to see. No extra *click* is required (this was Phase 1's own stated bar for freshness/fallback visibility), but the *scroll* distance to reach question B/C is real. | MINOR |
| 2 | Executive Decision's "Expected Result" field, when derived from a historical commit-message-shaped `pending_work`/`objective` string, reads awkwardly — a past-tense-sounding string templated into a future-facing sentence ("`milestone: Phase 3 local provider pipeline validated (...)` moves to a checkpoint-able state"). Understandable on a careful read (the "Next Action" line right above states the actual action plainly), but a real wording rough edge on the second most important card. Root cause is in `app.executive_decision`'s plan-text composition (business logic, not a template/frontend string), not a trivial presentation fix. | MINOR |
| 3 | "Where I Left Off" (ROLE_OS) and "What Matters Now" (ROLE Commerce Factory) name two different projects with two different recommended actions. This is intentional and correctly labeled (continuity vs. priority are different questions, per this module's own design brief), and Today's Focus's #1 item agrees with Executive Decision (no internal contradiction) — but a fast morning glance could read the first two cards as disagreeing about "what to do." | MINOR |
| 4 | No blocking, no high-value, no cosmetic-only-and-otherwise-irrelevant issues found. Quick Actions, Portfolio Ranking, Needs Attention, and the freshness/fallback badges all rendered correctly and matched their backend data exactly — no dead links, no empty states presented as real data, no silent fallback (Phase 0's original finding remains fixed). | NO ISSUE (everything else checked) |

No BLOCKING or HIGH VALUE findings.

## Change Filter

Applied to findings #1–#3 (the only candidates):

| Finding | Improves a daily question? | Reduces clicks/confusion? | Reuses existing backend truth? | Small? | Low maintenance burden? | Verdict |
|---|---|---|---|---|---|---|
| #1 (card height) | Marginally (B/C reachability) | Reduces scroll, not clicks (none exist to reduce) | Yes (pure layout) | Trimming would mean cutting real, non-filler content, or restructuring the dominant card's own information hierarchy — not "small" without reducing what Q1 already answers well | Yes if done at all | **Mixed — not a strong yes across the board** |
| #2 (wording) | Marginally (a card already answers B without needing this field) | No | No — the fix lives in `app.executive_decision`'s text composition, not a template string | No — business-logic change, not frontend-only | Unclear until scoped | **No** |
| #3 (two projects) | No — the distinction is intentional and already correctly labeled | No | N/A | N/A | N/A | **No — not a defect** |

None of the three clears the filter as a strongly-yes, safely-trivial change. Per Step 6/8's instruction, none is implemented.

## Decision

**A — NO CHANGE NEEDED.**

Mission Control already satisfies the daily-use goal: all four questions are answered clearly, with real evidence, with zero required clicks to *see* the answers and exactly one click to *act* on them (Resume Work). The friction found is real but consistently MINOR — a scroll-distance observation and a wording rough edge in a rarely-read sub-field — not a structural or Core-affecting problem, and none of it survives the strict change filter as a safely-trivial fix. Multi-Root Discovery (Task 2.1) has zero effect on Mission Control's output, confirmed both statically and live.

## Recommended Changes, If Any

None implemented. For the record (not tasked, not scheduled):
- Finding #2 (Expected Result wording) could be revisited if `app.executive_decision`'s plan-text composition is ever touched for an unrelated reason — not worth a dedicated task on its own given it's a single sub-field on one card, correctly superseded in clarity by the "Next Action" line directly above it.
- Finding #1 (card height/scroll) is a natural consequence of Primary Focus being deliberately "the one dominant card" (Sprint C5/C10's own design intent) — shrinking it would trade away real information for screen space, which is a worse trade, not a free win. Left as-is.

## Daily-Start Simulation

Scenario: Role opens the computer tomorrow morning, launches Role OS, with no memory of this conversation.

- **What project was he working on?** Yes — "Where I Left Off" names ROLE_OS immediately, first thing on the page.
- **What was happening?** Yes — status (`active`), last activity timestamp, and an 2-item "Recommended because" explanation are all present without scrolling.
- **What matters most?** Yes, one scroll away — Executive Decision names ROLE Commerce Factory with a plain-English reason, evidence, and an explicit confidence discount disclosed inline (since the underlying scan is 85.8h stale).
- **What should he do next?** Yes, one more scroll — three concrete, prioritized actions across three projects.
- **How to resume?** Yes — one click on "Resume Work →" from the very first card; the backend already has a complete, ready-to-paste prompt built (`resume_state.prompt`), confirmed present in the real payload, targeting `claude_code` as the recommended assistant.

**Result: PASS.** The one honest caveat surfaced by this simulation is *not* a Mission Control defect: the specific *next action text* for ROLE_OS ("fix: anchor runtime data paths...") is itself stale, because the Workspace scan hasn't been re-run since 2026-09-10 despite two real commits having landed since (`de242a0`, `f0b5a1a`) — but Mission Control is honest about this: the staleness banner is visible at the top of the page, and the Executive Decision card's own confidence is visibly discounted (0.72, not the un-discounted ~0.85 seen when fresh in Phase 1). This is a "remember to rescan" operational habit gap, not a Mission Control design defect — the honesty mechanism Phase 1 built for exactly this situation is working as designed.

## Risks / Limitations

- This review used one real, live snapshot of canonical data at one point in time (2026-09-14, ~04:49–04:53 UTC) — a different day's real data could surface different card lengths or a fresh (non-stale) scan; the structural findings (card order, card #1's height, the wording rough edge's root cause) are code-level facts, not time-dependent, so they remain valid regardless.
- Viewport testing was limited to two window sizes (1366×800, 1920×1080 — both via headless-window resize which produced identically-sized screenshots, suggesting the capture is bound by the extension's own viewport rather than the OS window; the structural conclusion — card #1 alone exceeds a ~780px content viewport — held in both attempts and is corroborated by the DOM's own element heights, so this is not considered a materially open question).
- No user (Role) was consulted directly during this evaluation; the daily-start simulation is a reasoned walkthrough of real data and real UI, not an observed live user session.

## Exact Next Task

Phase 2 — Documentation Reality Sync (`docs/ROLE_OS_2_PHASE_2_PLAN.md`, Task 2.3).
