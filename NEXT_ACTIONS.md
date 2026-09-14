# Role OS 2.0 — Next Actions

*This file describes NEXT. It is overwritten at every completed major task, not appended to. It is a short queue, not a roadmap — see `docs/ROLE_OS_2_PHASE_2_PLAN.md` for Phase 2's full task list and reasoning.*

## Now

**Phase 2 — Documentation Reality Sync**

Mission Control Daily-Use Gap Check is complete — see `docs/PHASE_2_MISSION_CONTROL_DAILY_USE_REVIEW.md`. Outcome A (no change needed): re-verified live against canonical data, all four daily questions (where did I leave off / what matters now / what's next / can I continue) scored CLEAR with zero required clicks, and Multi-Root Discovery confirmed to have no effect on Mission Control's output (adopted-only reasoning). Two MINOR, non-blocking findings were documented but not implemented (neither cleared the task's strict change filter as a safely-trivial fix).

Next: bring `README.md`/`ARCHITECTURE.md`/`app_version` (`dashboard/app/config.py`) in line with reality — Mission Control, Project Memory, Ecosystem, Impact Analysis, Executive Decision, and everything else Phase 1/2 built. Documentation-and-one-constant-only; no behavior change. This has not started yet.

## After That

Approved Phase 2 execution order (per Role's explicit approval), remaining:

1. **Documentation Reality Sync** (see above)
2. **Runtime Data Hygiene Bundle** — only the explicitly-approved-by-Role parts (see Blocked below); the rest stays deferred

## Blocked / Requires Role Decision

- `var/role_os_alpha/`'s disposition — **DEFER**, per Role's explicit instruction. Do not modify, migrate, delete, rename, or reinterpret it during Phase 2 without separate authorization.
- Whether to actually set `ROLE_OS_DISCOVERY_ROOTS` in any real running configuration, which of the 6 real, un-adopted projects (5 of which are now confirmed discoverable once it is set) to include, and whether to adopt any of them — **DO NOT ADOPT YET**; Task 2.1 only built and validated the capability, it did not enable it or adopt anything.
- Deleting the legacy `dashboard/var/role_os_dashboard/` copy — **DO NOT DELETE YET**, until provenance/migration documentation is sufficient and Role explicitly approves.
- Fixing ROLE MASTER's cosmetic status mismatch — **DEFER** unless it becomes relevant to an approved task; do not silently change project state.
- The Advisor vs. Operational Intelligence/Executive Decision overlap — **DEFER**; do not redesign or remove Advisor in Phase 2.
- `pi_ai_workspace` — **REVIEW ONLY** (data check, if the Hygiene Bundle task is reached); no removal without evidence and explicit approval.

## Do Not Do Yet

- Do not modify, migrate, delete, rename, or reinterpret `var/role_os_alpha/` under any circumstance without a separate, explicit Role authorization.
- Do not auto-adopt any of the 6 real projects outside the Discovery root, even after Multi-Root Discovery makes them visible.
- Do not delete the legacy `dashboard/var/role_os_dashboard/` copy without Role's explicit go-ahead.
- Do not change ROLE MASTER's status field without Role's explicit go-ahead.
- Do not redesign or remove Advisor.
- Do not remove `pi_ai_workspace` — review only, no removal in Phase 2.
- Do not treat `samples/role_os_sample/` as a production runtime source for anything.
- Do not delete or rewrite historical docs (`docs/PHASE_1_TASK_*.md`, `docs/PHASE_1_COMPLETION.md`, `docs/PHASE_2_TASK_*.md`, `audits/`, `docs/product/DECISIONS.md`, `docs/architecture/01`–`21`).
