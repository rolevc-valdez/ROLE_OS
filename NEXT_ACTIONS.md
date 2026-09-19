# Role OS 2.0 — Next Actions

*This file describes NEXT. It is overwritten at every completed major task, not appended to. It is a short queue, not a roadmap — see `docs/ROLE_OS_2_PHASE_2_PLAN.md` for Phase 2's full task list and reasoning.*

## Now

**Primary next action (the only one): Phase 3 — Task P3.1 — Daily Command Center Requirements / Data Gap Analysis.**

**NOT STARTED. WAIT FOR ROLE TO RETURN / AUTHORIZE IMPLEMENTATION.** Do not begin it on your own.

Scope and full task list: `docs/ROLE_OS_2_PHASE_3_SCOPE.md`. Phase 2 is COMPLETE (`docs/PHASE_2_COMPLETION.md`, checkpoint `20b80df`) and must not be repeated. Phase 3 is PLANNED — NOT STARTED.

## Blocked / Requires Role Decision (all DEFERRED, none approved)

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
- Do not start any speculative feature work; anything not chosen by Role during Phase 3 scoping stays deferred.
