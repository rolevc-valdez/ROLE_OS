# Role OS 2.0 — Phase 2 Plan

Status: **planning only**. No application code, runtime data, or living control file was changed in producing this document.

## 1. Phase 1 Starting Baseline

Phase 1 — Core Consolidation is complete (`docs/PHASE_1_COMPLETION.md`, commit `f2b87b0`). The five-stage core (`PROJECT → CURRENT STATE → NEXT ACTION → CONTEXT → RESUME WORK`) is real, working, and verified live: Mission Control answers all three questions against 5 real adopted projects and 7 Daily Session registry rows; staleness/fallback honesty is genuinely active; navigation is grouped into 5 clusters with all 32 routers intact; the legacy dashboard is archived; discovery reports are resolved; the full test suite (1,347 tests) passes; `CURRENT_STATE.md`/`NEXT_ACTIONS.md` provide verified continuity across a lost session. Eight items remain open, none blocking, all named explicitly in `docs/PHASE_1_COMPLETION.md`'s Remaining Issues table.

## 2. Phase 2 Objectives

Continue optimizing the same three questions Phase 1 established — **not** a general cleanup sprint, **not** an excuse to build every deferred idea. Every proposed task below exists because it either (a) closes a real gap in answering "Where did I leave off? / What matters now? / What's next?", or (b) removes a concrete, evidenced risk to data safety or maintainability. Nothing is proposed merely because it exists or would be technically satisfying to fix.

## 3. Explicit Non-Goals

- Not a redesign of Mission Control, Discovery, Workspace, or any Core module.
- Not a rewrite of the ~24-router surface Task 8/8B already simplified.
- Not a general "let's also fix everything else we noticed" sprint.
- Not adding new AI/LLM capability — the deterministic, no-hidden-weighting constraint remains non-negotiable (per `docs/architecture/01_VISION.md` and every subsequent decision record).
- Not resolving `var/role_os_alpha/` or the 6 out-of-scope real projects unilaterally — those are Role's decisions, not implementation tasks.
- Not retiring any capability (Advisor, Graph, Conversation Graph, `pi_ai_workspace`, etc.) — Phase 2 identifies candidates for *future* retirement, it does not execute any retirement.

## 4. Remaining-Issues Classification

| # | Issue | Class | Solves | Affects Core? | Affects user data? | Risk of leaving alone | Risk of changing | Simpler or more complex? | Recommendation |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `var/role_os_alpha/` disposition | **E** | Removes ambiguity about a data source's status | No (nothing reads it) | Potentially — contents may be real historical data | None (inert) | Discarding real data if wrong | Simpler if resolved | Ask Role directly; not an implementation task |
| 2 | Legacy `dashboard/var/role_os_dashboard/` copy | **B** | Removes a confusing, superseded duplicate of already-migrated data | No | No (source data is already safely duplicated in canonical location, per Task 3D's checksum-verified copy) | Low (disk clutter only) | None (already fully documented/copied) | Simpler | Delete once bundled into Task 2.5 below |
| 3 | 6 real projects outside Discovery root | **A** | Directly the "PROJECT" step of the core chain — Role OS is blind to real, active work | **Yes** — this is Core | No | Real: Mission Control cannot recommend/track work it never sees | Low if scoped as config-only (see Task 2.1) | Simpler for the user (their real projects become visible); slightly more config surface | Design + implement multi-root discovery (Task 2.1) |
| 4 | ROLE MASTER status mismatch | **C** | Cosmetic accuracy | No | Trivial | None | None | Neutral | Bundle into Task 2.5, lowest priority |
| 5 | `pi_ai_workspace` vs `pi_ai_sessions` | **C** | Removing dead legacy fields eventually | No (no evidence of active harm, Task 8) | Unknown until checked | Low | Unknown until data is checked | Simpler if ever removed | Defer; note in Task 2.5 as "check, don't remove" |
| 6 | `conftest.py` isolation gap | **B** | Test runs must not silently write to real runtime data | No (test-only) | **Yes** — pollutes real `role_os_assets.db` cache on every suite run | Low (cache-only) but real and repeated | None (mirrors existing isolation pattern for the other 10 vars) | Simpler, more correct | Fix directly (Task 2.4) |
| 7 | Stale `README.md`/`ARCHITECTURE.md` | **B** | A new reader (human or AI) materially misunderstands what exists | No (docs only) | No | Real — this is the exact Phase 0 finding that motivated Task 7's living files, still unresolved at the source | None (docs-only sync) | Simpler for anyone new | Fix directly (Task 2.3) |
| 8 | Stray git worktree / prune warning | **C** | Cosmetic git housekeeping noise | No | No | None (observed harmless across 15+ commits) | None | Neutral | Role runs `git worktree remove` manually whenever convenient; not a Role OS task at all |

## 5. Capability Assessment

**Directly support the Core:** Discovery (`app/discovery`), Workspace (`app/workspace`), Project Context (`app/project_context`), Project Memory (`app/project_memory` — internal, no dedicated router, correctly composed-in rather than a competing page), Resume Work (`app/workspace/resume.py`, `execution_target.py`), Mission Control, Operational Intelligence, Executive Decision, the canonical Projects DB (`pi_projects`/`pi_ai_sessions`/`pi_collections`/`pi_capabilities`/`pi_dependencies`/`pi_health`/`pi_reconciliation`).

**Useful supporting capabilities:** Project Ecosystem, Impact Analysis (feed Project Memory's bounded related-projects/impact section — real, but no UI destination of their own, correctly so), Assets OS (backs the shared filesystem walk every Core module reuses), Session/Daily Session (feeds Mission Control's `daily_session` card).

**Technically impressive but add complexity beyond what the Core needs:** Graph and Conversation Graph (two independent, deterministic knowledge-graph visualizations — genuinely well-built, genuinely not duplicative of each other, but neither is read by anything in the Core chain), the Imports/Extraction pipeline (a full ChatGPT-export ingestion + rule-based entity-extraction system, self-contained and well-isolated, but orthogonal to "resume my project work").

**A duplication Phase 1 did not fully examine — flagged here, not resolved:** `app/advisor` (Epic 2, the *original* recommendation engine, pre-dating Operational Intelligence and Executive Decision) may now substantially overlap in *purpose* (though not implementation) with Operational Intelligence → Executive Decision's later, more evidence-rigorous, more transparent scoring chain. Task 8's own overlap analysis examined OI vs. ED (found correctly layered) but never compared either against Advisor. This is a genuine open question, not a conclusion — Advisor is not recommended for retirement here; it's recommended for a dedicated, small evidence-gathering look in a later phase.

**Should remain available but receive no further development:** Graph, Conversation Graph, `app/advisor` (pending the overlap question above), Imports/Extraction, `pi_ai_workspace` (legacy v1.3 fields).

**Candidates for potential future retirement (not decided, not executed here):** `pi_ai_workspace`, pending a one-time check of whether any real project's data lives only there; `app/advisor`, pending the overlap evidence-gathering above.

## 6. Project Discovery — Analysis

**Current model:** one `ROLE_OS_DISCOVERY_ROOT` (default: this repo's parent, `1 - IA PROJECTS`), scanned to a configurable depth, with an extra-*exclusions* list (`ROLE_OS_DISCOVERY_EXTRA_EXCLUSIONS`) to narrow it further. There is no mechanism to widen it — a real project living anywhere else (confirmed: `role-content-factory`, `rolevaldez.com`, `SUPER-FACIL`, `AGUA-AZUL-APP`, `charcos-site`, `desierto-creativo-site`, all under `Documents\`) is structurally invisible to normal Role OS operation, discoverable only by manually re-running the Discovery CLI against that other root (as Task 9's archived report did, once, by hand).

**Options evaluated:**
- **Multiple configured discovery roots** — extend the existing scan to iterate a *list* of roots instead of one. Reuses the entire existing per-root scan pipeline unchanged, called N times instead of once; results merge into the same `DiscoveredProject` list Workspace already consumes. Smallest possible change; no new persistence, no new concept.
- **Explicit project registration** — a small allow-list of individual project *paths* (not roots) a user manually adds one at a time, independent of any scan root. More precise (avoids scanning unrelated sibling folders like `My Music`/`Documents`'s many non-project clutter), but is a new concept (a registry) layered on top of Discovery's existing "filesystem is the source of truth" design — more moving parts, a new small persisted list, a new UI affordance to add one.
- **Both** — rejected for Phase 2: two mechanisms doing overlapping jobs is exactly the complexity growth the operating principle ("simplicity > more features") warns against.

**Recommendation: multiple configured discovery roots**, not explicit registration. It is the smaller, simpler change — pure configuration plus an iteration change in existing scan code, no new UI, no new persisted concept, no new "is this project registered or not" second source of truth. The existing per-folder classification (Software Project / Mixed Project / Non-project) and health/move-risk scoring already correctly filter out clutter *within* whatever root is scanned (as proven by the archived `Documents` audit itself, which correctly flagged `ACID Pro 7.0 Projects`/`Audacity`/etc. as `Non-project`/`Archive`, not real projects) — so scanning an additional root does not require a new precision mechanism; Discovery already has one.

## 7. Mission Control — Daily-Use Evaluation

Evaluated whether the current implementation (verified live throughout Phase 1, most recently during Final Validation) requires navigating through several screens to answer the three questions. **Finding: no, it does not** — `GET /` already renders, on one screen, in this order: Where I Left Off (Primary Focus + Snapshot Continuity + Resume Work CTA), What Matters Now (Executive Decision + ecosystem-decisions fallback badge), What's Next (Today's Focus), with staleness/fallback already visible inline where relevant (confirmed live: a real stale state and a real fallback state were both observed and correctly displayed during Final Validation, with zero additional clicks required to see either). No redesign is proposed. The one concrete daily-use gap found — not a redesign, a small addition — is named as Task 2.2 below.

## 8. Proposed Phase 2 Tasks

**5 tasks**, ordered by dependency and risk (lowest-risk/most-foundational first):

### Task 2.1 — Multi-Root Discovery
**Why:** Role's real, active projects exist outside Role OS's single default scan root — a direct, evidenced gap in the "PROJECT" step of the core chain. Without this, Mission Control structurally cannot see or recommend work on those projects.
**Scope:** Extend `ROLE_OS_DISCOVERY_ROOT` to accept multiple roots (e.g. a `ROLE_OS_DISCOVERY_ROOTS` list, comma-separated, falling back to the single existing var for compatibility); iterate the existing scan pipeline once per root; merge results before they reach Workspace. No new persistence, no new UI concept, no change to classification/scoring logic.
**Touches Core:** Yes (Discovery). **Touches user data:** No (adds visibility, does not adopt anything automatically — adoption remains the existing explicit, manual step).

### Task 2.2 — Mission Control Daily-Use Gap Check
**Why:** Explicitly evaluate (not redesign) whether anything small is missing for genuinely frictionless daily use, now that the page has been exercised live across many real sessions in Phase 1.
**Scope:** A short, evidence-gathering pass (not a rebuild): confirm the three answers render above the fold on a typical viewport; confirm the Resume Work CTA is the single most visually prominent element; fix only what's found, with the smallest possible change (headings/CSS/layout only, matching Task 4's own established constraint). If nothing material is found, this task closes with "no change needed, documented."
**Touches Core:** No (presentation only). **Touches user data:** No.

### Task 2.3 — Documentation Reality Sync
**Why:** `README.md`/`ARCHITECTURE.md`/`app_version` remain stale from Phase 0 — the exact finding that motivated `CURRENT_STATE.md`'s creation, still unresolved at the source. A new reader hitting the front door first still gets a materially wrong picture.
**Scope:** Update `README.md`'s feature list and `ARCHITECTURE.md`'s module map to include Mission Control, Project Memory, Ecosystem, Impact Analysis, Executive Decision, and everything Phase 1 built; bump `app_version` in `dashboard/app/config.py` to reflect reality. Documentation-and-one-constant-only; no behavior change.
**Touches Core:** No. **Touches user data:** No.

### Task 2.4 — Test Isolation Hardening
**Why:** `conftest.py` isolates 10 of 12 dashboard-owned DB paths; the missing two (`ROLE_OS_ASSETS_DB_PATH`, `ROLE_OS_ECOSYSTEM_DB_PATH`) mean every full-suite run writes real cache rows into the actual runtime `role_os_assets.db` — confirmed repeatedly throughout this entire Phase 1 engagement.
**Scope:** Add the same `tempfile.mkdtemp()`-based `setdefault()` pattern already used for the other 10 variables. Mechanical, small, matches an existing, proven pattern exactly.
**Touches Core:** No (test infrastructure only). **Touches user data:** Prevents future incidental writes to it.

### Task 2.5 — Runtime Data Hygiene Bundle
**Why:** Three small, independently low-value-as-standalone-tasks items, bundled to avoid Phase 2 sprawl: (a) delete the confirmed-superseded `dashboard/var/role_os_dashboard/` legacy copy once Role confirms Task 3D/3C's checksum-verified migration record is sufficient provenance; (b) fix ROLE MASTER's cosmetic status mismatch; (c) run the one-time data check on `pi_ai_workspace` (does any real project have data only there?) and document the answer — without removing anything regardless of the answer.
**Scope:** Three small, independent, low-risk changes/checks, done together as one task to keep the overall task count small.
**Touches Core:** No. **Touches user data:** (a) requires Role's go-ahead first; (b)/(c) do not modify canonical adopted-project data beyond the one cosmetic field in (b), which Role should also explicitly approve given Task 6's original "do not overwrite" caution.

## 9. Task Dependencies / Order

1. **Task 2.4** (test isolation) — no dependencies, purely defensive, do first so nothing else risks further cache pollution during Phase 2's own testing.
2. **Task 2.1** (multi-root discovery) — no dependencies; the most Core-relevant, do next.
3. **Task 2.2** (Mission Control gap check) — best done after 2.1, since a new discovery root may surface new real projects worth checking Mission Control's rendering against.
4. **Task 2.3** (documentation sync) — best done last among the code-adjacent tasks, so it can describe 2.1/2.2's outcomes accurately rather than needing a second pass.
5. **Task 2.5** (hygiene bundle) — independent of the others; gated on Role's decisions for parts (a) and (b), can happen any time after those are given.

## 10. Risk Assessment

- **Task 2.1** carries the most real risk of the five (it touches Discovery), but is scoped to be purely additive (more roots scanned, same classification/scoring logic, no auto-adoption) — the actual risk is bounded to "Discovery takes longer" or "finds more Non-project clutter to filter," not data corruption.
- **Tasks 2.2, 2.3, 2.4** carry near-zero risk — presentation, documentation, and test-infrastructure changes respectively, none touching runtime data or Core logic.
- **Task 2.5** is the only task with any data-safety risk (part a, deleting a legacy copy) — explicitly gated on Role's approval before execution, per Phase 1's own established discipline for anything touching real or historical data.

## 11. User-Data Safety Rules

Carried forward unchanged from Phase 1's own proven discipline:
- No canonical database is written to except via existing application code paths (never manual SQL edits).
- No deletion of anything containing real or ambiguous-provenance data without an explicit, printed-before-execution proposal and Role's go-ahead (exactly Task 3C/3D's and Task 6's pattern).
- `var/role_os_alpha/` is not touched under any circumstance in Phase 2 without a separate, explicit Role decision.
- Every task that could incidentally write to real runtime data during its own validation must disclose exactly what changed, as every Phase 1 task did.

## 12. Testing Strategy

Same discipline as Phase 1: focused new tests per task, a relevant regression slice run per task (not the full 37–48 minute suite for every small change), and one full-suite run at Phase 2's own close (mirroring this Final Validation). Task 2.4 should be validated by confirming a fresh test run no longer touches `var/role_os_dashboard/role_os_assets.db`'s mtime.

## 13. Definition of Done

Phase 2 is done when: the 5 tasks above are complete and individually verified; the full test suite passes; `CURRENT_STATE.md`/`NEXT_ACTIONS.md` are refreshed to reflect the new state; a completion review (mirroring `docs/PHASE_1_COMPLETION.md`) confirms the integrated system — not just each task in isolation — still answers the three core questions correctly, including for any newly-discovered projects from Task 2.1.

## 14. Items Requiring Role's Decision

1. `var/role_os_alpha/`'s disposition (merge, archive, discard) — independent of Phase 2's task list.
2. Whether any of the 6 real, un-adopted projects should be added to the new multi-root discovery configuration once Task 2.1 exists (Task 2.1 only builds the *capability*; which roots to actually configure is Role's call).
3. Approval to delete the legacy `dashboard/var/role_os_dashboard/` copy (Task 2.5a).
4. Approval to fix ROLE MASTER's cosmetic status field (Task 2.5b).
5. Whether the Advisor-vs-Operational-Intelligence/Executive-Decision overlap question (Section 5) is worth a dedicated future look, or accepted as intentional redundancy.

## 15. Recommended First Task

**Task 2.4 — Test Isolation Hardening.** It is the smallest, lowest-risk, most mechanical of the five, directly prevents further incidental pollution of real runtime data during all subsequent Phase 2 work (including Task 2.1's own testing), and requires no Role decision to begin.

---

# PHASE 2 PLANNING COMPLETE

**Proposed task count:** 5

**Must-do tasks:** Task 2.1 (Multi-Root Discovery)

**Should-do tasks:** Task 2.3 (Documentation Reality Sync), Task 2.4 (Test Isolation Hardening)

**Optional/evaluation tasks:** Task 2.2 (Mission Control Daily-Use Gap Check — may close with "no change needed"), Task 2.5 (Runtime Data Hygiene Bundle — parts gated on Role approval)

**Deferred items:** `var/role_os_alpha/` disposition; the 6 out-of-scope real projects' eventual adoption; `pi_ai_workspace` retirement (pending data check only); Advisor-vs-OI/ED overlap question; stray git worktree cleanup

**Role decisions required:** 5 (listed in Section 13 above)

**Recommended Phase 2 first task:** Task 2.4 — Test Isolation Hardening
