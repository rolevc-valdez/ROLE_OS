# Role OS 2.0 — Next Actions

*This file describes NEXT. It is overwritten at every completed major task, not appended to. It is a short queue, not a roadmap — see `docs/ROLE_OS_2_PHASE_2_PLAN.md` for Phase 2's full task list and reasoning.*

## Now

**Phase 2 — Mission Control Daily-Use Gap Check**

Task 2.1 (Multi-Root Discovery) is complete — see `docs/PHASE_2_MULTI_ROOT_DISCOVERY.md`. `ROLE_OS_DISCOVERY_ROOTS` (comma-separated) now lets Discovery scan multiple explicitly-configured roots; validated live (read-only, isolated temp DB) that 5 of the 6 previously-invisible real projects become discoverable by adding `C:\Users\rolev\Documents` as a second root. Nothing was adopted; `ROLE_OS_DISCOVERY_ROOTS` is not yet set in any real running configuration — that, and any subsequent adoption, remain Role's decision.

Next: a short, evidence-gathering pass (not a redesign) — confirm the three Mission Control answers render above the fold on a typical viewport, confirm the Resume Work CTA is the single most visually prominent element, fix only what's found with the smallest possible change. May close with "no change needed, documented." This has not started yet.

## After That

Approved Phase 2 execution order (per Role's explicit approval), remaining:

1. **Mission Control Daily-Use Gap Check** (see above)
2. **Documentation Reality Sync** — bring `README.md`/`ARCHITECTURE.md`/`app_version` in line with reality
3. **Runtime Data Hygiene Bundle** — only the explicitly-approved-by-Role parts (see Blocked below); the rest stays deferred

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
