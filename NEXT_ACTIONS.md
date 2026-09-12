# Role OS 2.0 — Next Actions

*This file describes NEXT. It is overwritten at every completed major task, not appended to. It is a short queue, not a roadmap — see `docs/ROLE_OS_2_ARCHITECTURE_PROPOSAL.md` for the longer-range picture.*

## Now

**Phase 1 — Final Validation / Completion Review**

Every task explicitly scoped for Phase 1 (Tasks 1 through 9) is complete. This step is a full-suite regression pass and a final canonical-runtime smoke test across everything Phase 1 touched, followed by a single completion report closing out Phase 1 — before any Phase 2 planning begins. This has not started yet.

## After That

Phase 1's task queue is empty. What follows Final Validation is Phase 2 planning — not started, not scoped, and explicitly not to begin before Final Validation completes (see Do Not Do Yet below).

## Blocked / Requires Role Decision

- `var/role_os_alpha/`'s disposition (merge, archive, or discard) — see `CURRENT_STATE.md`'s Open Issues and `docs/RUNTIME_DATA_MAP.md`
- Whether any of the real, un-adopted projects outside the Discovery root (`role-content-factory`, `rolevaldez.com`, `SUPER-FACIL`, `AGUA-AZUL-APP`, `charcos-site`, `desierto-creativo-site`) should ever be brought into Role OS's scope
- ROLE MASTER's status mismatch (legacy "Completado" vs. canonical "active") — cosmetic, no urgency, but unresolved
- Whether `pi_ai_workspace` (superseded v1.3 AI fields) still holds any real data worth preserving before it's ever considered for removal (Task 8's REVIEW flag)

## Do Not Do Yet

- Do not migrate, merge, or delete `var/role_os_alpha/` without an explicit Role decision.
- Do not begin Phase 2 planning or work before Phase 1's Final Validation / Completion Review is done.
- Do not delete or rewrite historical docs (`docs/PHASE_1_TASK_*.md`, `audits/`, `docs/product/DECISIONS.md`, `docs/architecture/01`–`21`) — they are frozen record, not living documentation.
- Do not treat `samples/role_os_sample/` as a production runtime source for anything — it is fixture/demo data only, reachable only via explicit `ROLE_OS_WORKSPACE_DIR`/`ROLE_OS_*_DB_PATH` selection.
- Do not promote `project_ecosystem`/`impact_analysis` into primary navigation "just because" — Task 8 deliberately left them UNCERTAIN, not resolved.
