# Role OS 2.0 — Next Actions

*This file describes NEXT. It is overwritten at every completed major task, not appended to. It is a short queue, not a roadmap — see `docs/ROLE_OS_2_ARCHITECTURE_PROPOSAL.md` for the longer-range picture.*

## Now

**Phase 2 Planning / Scope Definition**

Phase 1 — Core Consolidation is complete and accepted (`docs/PHASE_1_COMPLETION.md`). No Phase 2 work has been scoped or started. Before any Phase 2 implementation begins, define what Phase 2 actually covers — this is a planning/scoping task, not a license to start building. Two categories of input should shape that scope: (a) the Remaining Issues table in `docs/PHASE_1_COMPLETION.md` (technical debt and Role-decision items), and (b) `docs/ROLE_OS_2_ARCHITECTURE_PROPOSAL.md`'s longer-range picture, which was never fully implemented in Phase 1 (Phase 1 deliberately scoped only the core-consolidation subset).

## After That

Not yet defined — depends entirely on Phase 2's scoping outcome. Do not pre-commit to a specific task list here; that would defeat the purpose of a scoping step.

Candidate low-risk starting points, evidence-based from Phase 1's own findings (not a commitment, just visible options for the scoping conversation):
- `conftest.py`'s Assets/Ecosystem DB test-isolation gap (small, self-contained, zero user-facing risk)
- A documentation-sync pass on `README.md`/`ARCHITECTURE.md`/`app_version`

## Blocked / Requires Role Decision

- `var/role_os_alpha/`'s disposition (merge, archive, or discard) — see `CURRENT_STATE.md`'s Open Issues and `docs/RUNTIME_DATA_MAP.md`
- Whether any of the 6 real, un-adopted projects outside the Discovery root should ever be brought into Role OS's scope
- ROLE MASTER's status mismatch (legacy "Completado" vs. canonical "active") — cosmetic, no urgency, but unresolved
- Whether `pi_ai_workspace` (superseded v1.3 AI fields) still holds any real data worth preserving before it's ever considered for removal

These should ideally be resolved with Role *before* Phase 2's scope is finalized, since they could materially change what Phase 2 needs to account for.

## Do Not Do Yet

- Do not begin any Phase 2 implementation before Phase 2 is actually scoped.
- Do not migrate, merge, or delete `var/role_os_alpha/` without an explicit Role decision.
- Do not delete or rewrite historical docs (`docs/PHASE_1_TASK_*.md`, `docs/PHASE_1_COMPLETION.md`, `audits/`, `docs/product/DECISIONS.md`, `docs/architecture/01`–`21`) — they are frozen record, not living documentation.
- Do not treat `samples/role_os_sample/` as a production runtime source for anything — it is fixture/demo data only, reachable only via explicit `ROLE_OS_WORKSPACE_DIR`/`ROLE_OS_*_DB_PATH` selection.
- Do not assume Phase 1's technical debt items are urgent — none of them blocked Phase 1's completion, and none should silently become Phase 2's forced starting point without a deliberate decision.
