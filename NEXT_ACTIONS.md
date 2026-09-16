# Role OS 2.0 — Next Actions

*This file describes NEXT. It is overwritten at every completed major task, not appended to. It is a short queue, not a roadmap — see `docs/ROLE_OS_2_PHASE_2_PLAN.md` for Phase 2's full task list and reasoning.*

## Now

**Phase 2 — Runtime Data Hygiene Bundle, parts (a)/(b) — both still BLOCKED on Role's explicit go-ahead**

Part (c) is complete — see `docs/PHASE_2_PI_AI_WORKSPACE_REVIEW.md`. `pi_ai_workspace` (v1.3) vs. `pi_ai_sessions`/`ai_session_snapshots` (v1.4): resolved as Legacy + Current, not a duplicate. `ai_workspace` has 0 live rows in every canonical database checked and zero callers outside its own isolated router; `ai_sessions` is the active, sole source for Resume Work/Mission Control. Recommendation: deprecate `ai_workspace` in a future, separately-approved task — **no removal, deprecation marking, or code change was made in this task.**

Remaining: (a) delete the legacy `dashboard/var/role_os_dashboard/` copy, (b) fix ROLE MASTER's cosmetic status mismatch. **Both remain blocked** — Role has not given the explicit go-ahead for either (see below). Until one is given, there is no further actionable Phase 2 task.

## After That

**Runtime Data Hygiene Bundle is the last task currently in the approved plan** (`docs/ROLE_OS_2_PHASE_2_PLAN.md`). With part (c) done and parts (a)/(b) still blocked, Phase 2's next actionable step — if Role does not approve (a) or (b) — is its own closing steps: a full-suite test run, refreshing `CURRENT_STATE.md`/`NEXT_ACTIONS.md` to reflect Phase 2 as complete, and a completion review mirroring `docs/PHASE_1_COMPLETION.md` (per `docs/ROLE_OS_2_PHASE_2_PLAN.md` §13, Definition of Done) — the plan's own closing criteria, not a new task invented to keep moving.

## Blocked / Requires Role Decision

- `var/role_os_alpha/`'s disposition — **DEFER**, per Role's explicit instruction. Do not modify, migrate, delete, rename, or reinterpret it during Phase 2 without separate authorization.
- Whether to actually set `ROLE_OS_DISCOVERY_ROOTS` in any real running configuration, which of the 6 real, un-adopted projects (5 of which are now confirmed discoverable once it is set) to include, and whether to adopt any of them — **DO NOT ADOPT YET**; Task 2.1 only built and validated the capability, it did not enable it or adopt anything.
- Deleting the legacy `dashboard/var/role_os_dashboard/` copy — **DO NOT DELETE YET**, until provenance/migration documentation is sufficient and Role explicitly approves.
- Fixing ROLE MASTER's cosmetic status mismatch — **DEFER** unless it becomes relevant to an approved task; do not silently change project state.
- The Advisor vs. Operational Intelligence/Executive Decision overlap — **DEFER**; do not redesign or remove Advisor in Phase 2.
- `pi_ai_workspace` — review complete (`docs/PHASE_2_PI_AI_WORKSPACE_REVIEW.md`): Legacy + Current, recommended for future deprecation. **Deprecation marking and removal are both a separate, not-yet-approved task** — no action taken here beyond the analysis itself.
- Whether to design/implement an explicit-project-registration Discovery mechanism (for isolated repositories like `bolsa-de-trabajo` that sit directly under a broad, mixed-use parent like the user home directory) — **NOT SCOPED**, noted as a future Discovery enhancement only (`docs/PHASE_2_MISSION_CONTROL_DAILY_USE_REVIEW.md`, "Discovery / Isolated Repository Note"); not part of Phase 2.

## Do Not Do Yet

- Do not modify, migrate, delete, rename, or reinterpret `var/role_os_alpha/` under any circumstance without a separate, explicit Role authorization.
- Do not auto-adopt any of the 6 real projects outside the Discovery root, even after Multi-Root Discovery makes them visible.
- Do not delete the legacy `dashboard/var/role_os_dashboard/` copy without Role's explicit go-ahead.
- Do not change ROLE MASTER's status field without Role's explicit go-ahead.
- Do not redesign or remove Advisor.
- Do not remove, deprecate-mark, rename, or modify `pi_ai_workspace`/`ai_workspace` without a separate, explicit Role authorization — the review (`docs/PHASE_2_PI_AI_WORKSPACE_REVIEW.md`) recommends eventual deprecation but does not approve acting on it.
- Do not treat `samples/role_os_sample/` as a production runtime source for anything.
- Do not delete or rewrite historical docs (`docs/PHASE_1_TASK_*.md`, `docs/PHASE_1_COMPLETION.md`, `docs/PHASE_2_TASK_*.md`, `audits/`, `docs/product/DECISIONS.md`, `docs/architecture/01`–`21`).
