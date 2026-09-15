# Role OS 2.0 — Next Actions

*This file describes NEXT. It is overwritten at every completed major task, not appended to. It is a short queue, not a roadmap — see `docs/ROLE_OS_2_PHASE_2_PLAN.md` for Phase 2's full task list and reasoning.*

## Now

**Phase 2 — Runtime Data Hygiene Bundle (Role-approved parts only)**

Documentation Reality Sync is complete — see `docs/PHASE_2_DOCUMENTATION_REALITY_SYNC.md`. `README.md`, `ARCHITECTURE.md`, and `dashboard/README.md` now accurately describe Role OS 2.0 (Mission Control as canonical landing page, Discovery/Multi-Root Discovery, Workspace Adoption, Project Context, Resume Work, Operational Intelligence/Executive Decision) instead of only the v1.x layer; `app_version` bumped `1.1.0` → `1.2.0` (the task's one pre-approved code change, focused regression-tested, 68 passed). Two historical docs got short correction notes without being rewritten.

Next: the last remaining Phase 2 task per the approved plan (`docs/ROLE_OS_2_PHASE_2_PLAN.md`, Task 2.5) is three bundled items — (a) delete the legacy `dashboard/var/role_os_dashboard/` copy, (b) fix ROLE MASTER's cosmetic status mismatch, (c) a one-time check of whether any real project's data lives only in `pi_ai_workspace` (review only, no removal). **Parts (a) and (b) remain blocked on Role's explicit go-ahead** (see below) — only part (c) can proceed without further approval. This has not started yet.

## After That

Approved Phase 2 execution order (per Role's explicit approval): **Runtime Data Hygiene Bundle is the last task currently in the approved plan.** Once its Role-approved parts are done (or explicitly deferred further), Phase 2's closing steps are: a full-suite test run, refreshing `CURRENT_STATE.md`/`NEXT_ACTIONS.md` to reflect Phase 2 as complete, and a completion review mirroring `docs/PHASE_1_COMPLETION.md` (per `docs/ROLE_OS_2_PHASE_2_PLAN.md` §13, Definition of Done) — not a new task to invent, the plan's own closing criteria.

## Blocked / Requires Role Decision

- `var/role_os_alpha/`'s disposition — **DEFER**, per Role's explicit instruction. Do not modify, migrate, delete, rename, or reinterpret it during Phase 2 without separate authorization.
- Whether to actually set `ROLE_OS_DISCOVERY_ROOTS` in any real running configuration, which of the 6 real, un-adopted projects (5 of which are now confirmed discoverable once it is set) to include, and whether to adopt any of them — **DO NOT ADOPT YET**; Task 2.1 only built and validated the capability, it did not enable it or adopt anything.
- Deleting the legacy `dashboard/var/role_os_dashboard/` copy — **DO NOT DELETE YET**, until provenance/migration documentation is sufficient and Role explicitly approves.
- Fixing ROLE MASTER's cosmetic status mismatch — **DEFER** unless it becomes relevant to an approved task; do not silently change project state.
- The Advisor vs. Operational Intelligence/Executive Decision overlap — **DEFER**; do not redesign or remove Advisor in Phase 2.
- `pi_ai_workspace` — **REVIEW ONLY** (data check, if the Hygiene Bundle task is reached); no removal without evidence and explicit approval.
- Whether to design/implement an explicit-project-registration Discovery mechanism (for isolated repositories like `bolsa-de-trabajo` that sit directly under a broad, mixed-use parent like the user home directory) — **NOT SCOPED**, noted as a future Discovery enhancement only (`docs/PHASE_2_MISSION_CONTROL_DAILY_USE_REVIEW.md`, "Discovery / Isolated Repository Note"); not part of Phase 2.

## Do Not Do Yet

- Do not modify, migrate, delete, rename, or reinterpret `var/role_os_alpha/` under any circumstance without a separate, explicit Role authorization.
- Do not auto-adopt any of the 6 real projects outside the Discovery root, even after Multi-Root Discovery makes them visible.
- Do not delete the legacy `dashboard/var/role_os_dashboard/` copy without Role's explicit go-ahead.
- Do not change ROLE MASTER's status field without Role's explicit go-ahead.
- Do not redesign or remove Advisor.
- Do not remove `pi_ai_workspace` — review only, no removal in Phase 2.
- Do not treat `samples/role_os_sample/` as a production runtime source for anything.
- Do not delete or rewrite historical docs (`docs/PHASE_1_TASK_*.md`, `docs/PHASE_1_COMPLETION.md`, `docs/PHASE_2_TASK_*.md`, `audits/`, `docs/product/DECISIONS.md`, `docs/architecture/01`–`21`).
