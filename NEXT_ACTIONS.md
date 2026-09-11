# Role OS 2.0 — Next Actions

*This file describes NEXT. It is overwritten at every completed major task, not appended to. It is a short queue, not a roadmap — see `docs/ROLE_OS_2_ARCHITECTURE_PROPOSAL.md` for the longer-range picture.*

## Now

**Phase 1 — Task 9: Discovery Report Artifacts**

Decide the fate of `var/discovery_reports/documents/` — generated report artifacts (`documents_audit.json`/`.md`) with no current router consumer (flagged since Task 3). Either wire them to a real, current consumer, or remove them as regenerable/obsolete. This is a small, self-contained decision-and-cleanup task, not a redesign.

## After That

Known remaining Phase 1 work, in order:

1. **Task 9** — Discovery Report Artifacts (see above)
2. **Phase 1 validation** — a full-suite regression pass and a final canonical-runtime smoke test across everything Phase 1 touched
3. **Phase 1 completion report** — a single summary closing out Phase 1 before any Phase 2 planning begins

## Blocked / Requires Role Decision

- `var/role_os_alpha/`'s disposition (merge, archive, or discard) — see `CURRENT_STATE.md`'s Open Issues and `docs/RUNTIME_DATA_MAP.md`
- `var/discovery_reports/documents/`'s fate (Task 9 needs this decided, or needs to make the recommendation itself)
- Whether `role-content-factory`/`subir-libros-etsy` should ever be brought into Role OS's Discovery scope
- ROLE MASTER's status mismatch (legacy "Completado" vs. canonical "active") — cosmetic, no urgency, but unresolved
- Whether `pi_ai_workspace` (superseded v1.3 AI fields) still holds any real data worth preserving before it's ever considered for removal (Task 8's REVIEW flag)

## Do Not Do Yet

- Do not migrate, merge, or delete `var/role_os_alpha/` without an explicit Role decision.
- Do not begin Phase 2 (or any work beyond the Phase 1 task list above) before Phase 1's validation and completion report.
- Do not delete or rewrite historical docs (`docs/PHASE_1_TASK_*.md`, `audits/`, `docs/product/DECISIONS.md`, `docs/architecture/01`–`21`) — they are frozen record, not living documentation.
- Do not treat `samples/role_os_sample/` as a production runtime source for anything — it is fixture/demo data only, reachable only via explicit `ROLE_OS_WORKSPACE_DIR`/`ROLE_OS_*_DB_PATH` selection.
- Do not promote `project_ecosystem`/`impact_analysis` into primary navigation "just because" — Task 8 deliberately left them UNCERTAIN, not resolved.
