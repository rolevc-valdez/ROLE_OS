# Role OS 2.0 — Next Actions

*This file describes NEXT. It is overwritten at every completed major task, not appended to. It is a short queue, not a roadmap — see `docs/ROLE_OS_2_PHASE_2_PLAN.md` for Phase 2's full task list and reasoning.*

## Now

**Phase 2's closing validation** (not yet started)

The Runtime Data Hygiene Bundle is fully complete — all three parts done:
- (c) `pi_ai_workspace` review — see `docs/PHASE_2_PI_AI_WORKSPACE_REVIEW.md`. Resolved as Legacy + Current; recommendation (deprecate, in a future separately-approved task) not acted on here.
- (a) Legacy `dashboard/var/role_os_dashboard/` copy — **deleted**, see `docs/PHASE_2_RUNTIME_DATA_HYGIENE.md`. A full read-only comparison proved every remaining difference from canonical was debug/test data; canonical already had all real user data since Task 3D.
- (b) ROLE MASTER status mismatch — **resolved, no change needed**. Current project evidence confirms canonical `"active"` is correct; the legacy "Completado" described a completed version milestone, not project closure.

**This was the last task in Phase 2's approved plan** (`docs/ROLE_OS_2_PHASE_2_PLAN.md`). Next: Phase 2's own closing steps — a full-suite test run, a final `CURRENT_STATE.md`/`NEXT_ACTIONS.md` refresh to mark Phase 2 complete, and a completion review mirroring `docs/PHASE_1_COMPLETION.md` (per §13, Definition of Done). **Not started in this task, per its explicit instruction not to begin closing validation.**

## After That

Phase 2 closing validation (see above) is the only remaining step before Phase 2 is formally complete. No Phase 3 task exists yet — one should not be invented here; it would be scoped after Phase 2's completion review.

## Blocked / Requires Role Decision

- `var/role_os_alpha/`'s disposition — **DEFER**, per Role's explicit instruction. Do not modify, migrate, delete, rename, or reinterpret it during Phase 2 without separate authorization.
- Whether to actually set `ROLE_OS_DISCOVERY_ROOTS` in any real running configuration, which of the 6 real, un-adopted projects (5 of which are now confirmed discoverable once it is set) to include, and whether to adopt any of them — **DO NOT ADOPT YET**; Task 2.1 only built and validated the capability, it did not enable it or adopt anything.
- The Advisor vs. Operational Intelligence/Executive Decision overlap — **DEFER**; do not redesign or remove Advisor in Phase 2.
- `pi_ai_workspace` — review complete (`docs/PHASE_2_PI_AI_WORKSPACE_REVIEW.md`): Legacy + Current, recommended for future deprecation. **Deprecation marking and removal are both a separate, not-yet-approved task** — no action taken here beyond the analysis itself.
- Whether to design/implement an explicit-project-registration Discovery mechanism (for isolated repositories like `bolsa-de-trabajo` that sit directly under a broad, mixed-use parent like the user home directory) — **NOT SCOPED**, noted as a future Discovery enhancement only (`docs/PHASE_2_MISSION_CONTROL_DAILY_USE_REVIEW.md`, "Discovery / Isolated Repository Note"); not part of Phase 2.

## Do Not Do Yet

- Do not modify, migrate, delete, rename, or reinterpret `var/role_os_alpha/` under any circumstance without a separate, explicit Role authorization.
- Do not auto-adopt any of the 6 real projects outside the Discovery root, even after Multi-Root Discovery makes them visible.
- Do not redesign or remove Advisor.
- Do not remove, deprecate-mark, rename, or modify `pi_ai_workspace`/`ai_workspace` without a separate, explicit Role authorization — the review (`docs/PHASE_2_PI_AI_WORKSPACE_REVIEW.md`) recommends eventual deprecation but does not approve acting on it.
- Do not treat `samples/role_os_sample/` as a production runtime source for anything.
- Do not delete or rewrite historical docs (`docs/PHASE_1_TASK_*.md`, `docs/PHASE_1_COMPLETION.md`, `docs/PHASE_2_TASK_*.md`, `audits/`, `docs/product/DECISIONS.md`, `docs/architecture/01`–`21`).
