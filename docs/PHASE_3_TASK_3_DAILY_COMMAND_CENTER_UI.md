# Role OS 2.0 — P3.3 Daily Command Center UI

*Implementation record. Builds the first usable Daily Command Center on the existing Mission Control landing route. No new app, dashboard, recommendation engine, persistence system, or entity.*

**Baseline:** `62be54c` (P3.2 complete). **Role's decisions applied:** the five adopted projects are `ROLE PERSONAL / project` (ROLE_KNOWLEDGE_OS included — its domain describes the product, not the subjects inside it); `kind = tool` must not compete in the primary work ranking; Dashboard v2 (`#/dashboard`, `GET /dashboard/summary`) is the canonical Role Dashboard.

## Implemented Layout

Route `/` (→ `#/home` → Mission Control, unchanged mechanism). Top to bottom:

1. **ROLE OS · Daily Command Center** + the existing stale-data banner
2. **Domain filter chips:** All · KONTOOR · UNGER · ROLE PERSONAL · CLIENTES (with counts); an *Unclassified* chip appears (dashed, secondary) only when unclassified work exists
3. **What should I do now?** — recommended item (domain tag, evidence-backed badges, next action with provenance, **Why** bullets, staleness note, large **Continue Working →** button) plus up to two "Then" cards
4. **Needs Attention** (existing Operational Intelligence list, moved up)
5. **Pending Work / Next Actions**
6. **Active Projects** | **Completed**
7. **Tools** | **Role Dashboard** (**Open Role Dashboard →**)
8. **Where I Left Off** (existing Primary Focus + Saved Snapshot) and **Daily Session** (existing)
9. A collapsed **Full analysis** panel holding every previous section unchanged (What Matters Now incl. the Executive Decision card, What's Next, Portfolio Ranking, Since Last Time, Recent Activity, Value Signal, Quick Actions, Portfolio strip)

## Reused Components / Services

Everything is still one `GET /mission-control` payload and the same SPA. Reused verbatim: `mcPrimaryFocusHtml`, `mcExecutiveDecisionHtml`, `mcNeedsAttentionListHtml`, `mcSnapshotContinuityHtml`, `mcDailySessionHtml`, `triggerResumeWork` (the one Resume Work mechanism), `renderDashFreshnessBanner`, `badgeHtml`/`healthBadge`, the existing card/grid/`u-*` classes and colour tokens. CSS added: ~70 lines in `components.css` using only existing tokens (chips, domain tags, larger button, why-list, details panel). The four domains map onto the existing palette (KONTOOR info-cyan, UNGER orange, ROLE PERSONAL brand-blue, CLIENTES green).

**Backend (additive):** `mission_control/service.py` gains a `work` block — `domains`, `active_projects`, `completed_projects`, `tools`, `role_dashboard` — built by `_work_groups()` purely from data already computed in the request (ProjectContexts, the Executive Decision ranking, Operational Intelligence recommendations). No new score or engine. Each item carries `domain`, `client_name`, `kind`, `status`, `rank`, `badges`, `why[]`, `next_action {text, source, inferred}`, `pending_work`, `days_since_activity`, `resume_available`. All previous payload keys are unchanged.

## Domain Filtering

Client-side, over the already-grouped payload (`dccMatchesFilter`); no refetch, no re-ranking, global navigation untouched. Filtering affects *What should I do now*, *Pending Work*, *Active*, *Completed* and *Tools*; *Where I Left Off* and the session/analysis areas stay global. The four domain names come from the payload (`work.domains`), not a hard-coded copy. Selecting a domain with no work shows "No projects in this domain."; other domains are never hidden.

## Classification Persistence

Applied through the application's own `PATCH /workspace/discovered/{id}` (validated by the P3.2 model), against the canonical runtime, after verifying the adopted set was exactly the five expected projects: ROLE_OS, ROLE Commerce Factory, ROLE MASTER, role-ecosystem, ROLE_KNOWLEDGE_OS → `domain = ROLE PERSONAL`, `kind = project`, `client_name = NULL`. Verified: 5 rows before and after; `id`, `status` (all still `active`, ROLE MASTER included), `priority`, `business_value`, `tags`, `notes`, `adopted_at`, `canonical_project_id` byte-identical; `PRAGMA integrity_check` ok. No SQLite hand-editing. The P3.2 schema migration (additive columns) was applied to the canonical `role_os_workspace.db` automatically by the app on this first run.

## Recommendation Behaviour

Source: the existing Executive Decision ranking (`active_projects` are listed in that rank order; the UI never re-ranks; rank 1 equals the Executive Decision winner). **Why** is assembled from real signals only: the top Operational Intelligence suggestion, whether a next action exists (and whether it was *inferred*), recorded pending work, blocked status, recency/staleness (same 30-day threshold the ranking uses), and high/critical business value. No score is shown ("66.7 pts" remains only in the collapsed Full analysis, where it already lived). Badges shown are only the evidence-backed ones: STALE, NEEDS ATTENTION, IMPORTANT, BLOCKED, PAUSED, ARCHIVED. **URGENT, QUICK WIN and WAITING are not shown and no Quick Wins section exists** — no real data supports them. Wording is "Pending Work / Next Actions"; the word "Tasks" is not used.

## Tools

`kind = tool` items are excluded from every recommendation source (Executive Decision, Workspace and Operational Intelligence advisors, "project to continue"/Primary Focus, Today's Focus, Needs Attention) via one shared predicate (`classification.is_rank_excluded`), and appear in **Tools**. Zero tools are persisted, so the section shows "No tools registered yet." — yt-dlp and Cobalt were deliberately not created.

## Completed

`status = completed` (P3.2 semantics) items appear in **Completed** (a completed tool is listed there, not under Tools) and stay out of every recommendation. Zero exist, so the section shows "No completed projects yet." Nothing was marked completed for demonstration. `archived` stays an active-list item with an ARCHIVED badge and its existing penalty.

## Provenance / Fallback Honesty

Next actions show their source; low-confidence ones (`latest git commit`, `CHANGELOG unreleased`) carry an **inferred** badge. Pending work is labelled "from last session". The page-level stale banner and a stale note on the recommendation itself remain; the Executive Decision card's own note, the ecosystem-decision "Fallback snapshot" badge and the "historical" snapshot badge are unchanged.

## Role Dashboard Integration

Canonical = Dashboard v2. **Open Role Dashboard →** (visible, secondary to Continue Working) navigates to `#/dashboard`. Verified live: hash `#/dashboard`, the view loads (`Dashboard`, `Portfolio Status`, `Continue Work`, `Needs Attention`) and the browser made `GET /dashboard/summary → 200`. Dashboard v2 was not modified or duplicated.

## Empty States

"No completed projects yet." · "No tools registered yet." · "No projects in this domain." (+ per-section domain variants) · "No next action available." · "No resumable session available." · "No active projects yet." · "No recommendation yet" (existing). No sample data in normal runtime.

## Tests

`dashboard/tests/test_daily_command_center.py` — 22 tests: grouping (active / completed / tool / completed-tool), domain + client flow, unclassified representable, paused/blocked/archived semantics and badges, no fabricated URGENT/QUICK WIN/WAITING, tools and completed excluded from ranking / decision / primary focus / Today's Focus / Needs Attention while remaining queryable, ranking order, next-action provenance, plain-language *why* (no score fragments), approved classification persists without touching status/priority/notes/ids, other domains empty, Role Dashboard link and `/dashboard/summary`, Resume Work, and UI string checks (IA order, filters, empty states, Continue Working wiring, no scores/"Tasks", inferred labelling, stale/fallback preserved, all existing sections still rendered). All previously existing Mission Control UI/API tests pass **unmodified**.

Results: full suite split as before — `tests/` 8, `builder/tests/` 26, `dashboard/tests/` 1,392 → **1,426 passed, 0 failed** (1,404 + 22).

## Runtime Safety

SHA256/size/mtime of all 15 runtime DB files were identical before and after the full test run (Test Isolation holds). The subsequent live run against the canonical runtime — which was expected to change `role_os_workspace.db` (migration + the five approved classifications) — also changed three other files as ordinary side effects of running the app, not of this task's code: `role_os_advisor.db` (the Advisor regenerates its `recommendations` cache), `role_os_assets.db` (asset cache refresh) and the external `role_os_projects.db` (app-managed, opened read-write). Row counts there are unchanged (projects 10, ai_sessions 6, snapshots 1, capabilities 0, dependencies 0, workspaces 7) and `integrity_check` is ok on all. `var/role_os_alpha/` untouched. The server was started with the repo's own launcher and stopped with its stop script afterward.

## Live Validation (canonical runtime)

`/` loaded the Daily Command Center. Chips: All 5 · KONTOOR 0 · UNGER 0 · ROLE PERSONAL 5 · CLIENTES 0. Recommended: ROLE Commerce Factory (ROLE PERSONAL; STALE, NEEDS ATTENTION; next action "milestone: Phase 3 local provider pipeline validated…" — *inferred from latest git commit*; why: suggested "Consider shipping/launching", has a next action, no activity in 31 days), then ROLE_OS and role-ecosystem. Pending Work listed four projects with sources (git commit ×2, ai_session, TODO.md) plus role-ecosystem's recorded pending work. All five projects under ROLE PERSONAL; KONTOOR/UNGER/CLIENTES → "No projects in this domain."; Completed → "No completed projects yet."; Tools → "No tools registered yet."; Where I Left Off → role-ecosystem with its saved snapshot. **Continue Working** rendered enabled (resumable context exists). It was **not clicked** against canonical data: doing so would create a real AI session record and may launch an external assistant; its backend and wiring are covered by tests (Resume Work API, single shared `triggerResumeWork` binding). The stale banner ("Workspace scan is 271h old") displayed correctly.

## Remaining Limitations

- The Executive Decision ranking reads the PI project's status (default `active`) ahead of the adoption overlay's status, so an overlay status of `paused`/`blocked` may not yet change the *score*; the Daily Command Center badges use the overlay status Role edits. Pre-existing behaviour, deliberately not altered here.
- All five projects show NEEDS ATTENTION and most STALE — that is what the existing engines currently report on a 271-hour-old scan; a rescan is the fix, not a UI change.
- Most next actions are inferred from git commits; recorded `NEXT_ACTION.md`/snapshots would sharpen the page.
- `business_value`/`priority` are still `medium` everywhere, so IMPORTANT never appears yet.
- No UI to classify/complete/mark tools (still via `PATCH /workspace/discovered/{id}`); no URGENT/QUICK WIN (needs due dates/effort data); no tool registration; visual check was done at a narrow browser viewport only.
- Not started: explicit project registration (P3.4), `ROLE_PROJECT.md` (P3.5), Windows startup (P3.6).
