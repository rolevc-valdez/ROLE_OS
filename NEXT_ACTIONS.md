# Role OS 2.0 — Next Actions

*This file describes NEXT. It is overwritten at every completed major task, not appended to. It is a short queue, not a roadmap — see `docs/ROLE_OS_2_PHASE_2_PLAN.md` for Phase 2's full task list and reasoning.*

## Now

**Phase 2 — Multi-Root Discovery**

The only task in Phase 2 classified **A — MUST DO**. Role's real, active projects exist outside Role OS's single default Discovery scan root (confirmed: `role-content-factory`, `rolevaldez.com`, `SUPER-FACIL`, `AGUA-AZUL-APP`, `charcos-site`, `desierto-creativo-site`, all under `Documents\`) — a direct gap in the "PROJECT" step of the core chain. Scope (per the approved plan): extend `ROLE_OS_DISCOVERY_ROOT` to accept multiple roots, reusing the existing per-root scan pipeline unchanged, called once per root, merging results before Workspace sees them. No new persistence, no new UI concept, no auto-adoption of anything found. This has not started yet.

## After That

Approved Phase 2 execution order (per Role's explicit approval), remaining:

1. **Multi-Root Discovery** (see above)
2. **Mission Control Daily-Use Gap Check** — a short evidence-gathering pass (not a redesign); may close with "no change needed"
3. **Documentation Reality Sync** — bring `README.md`/`ARCHITECTURE.md`/`app_version` in line with reality
4. **Runtime Data Hygiene Bundle** — only the explicitly-approved-by-Role parts (see Blocked below); the rest stays deferred

## Blocked / Requires Role Decision

- `var/role_os_alpha/`'s disposition — **DEFER**, per Role's explicit instruction. Do not modify, migrate, delete, rename, or reinterpret it during Phase 2 without separate authorization.
- Which of the 6 real, un-adopted projects (if any) get added to the new multi-root discovery configuration, and whether to adopt them — **DO NOT ADOPT YET**; Multi-Root Discovery only makes them discoverable, adoption is a separate later decision.
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
