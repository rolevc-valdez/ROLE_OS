# Role OS 2.0 — Next Actions

*This file describes NEXT. It is overwritten at every completed major task, not appended to. It is a short queue, not a roadmap — see `docs/ROLE_OS_2_ARCHITECTURE_PROPOSAL.md` for the longer-range picture.*

## Now

**Phase 1 — Task 8: Navigation Simplification Analysis**

Analyze the ~24 top-level routers currently mounted in `dashboard/app/main.py` and propose which should remain independent nav items versus become drill-downs reachable from Mission Control — per `docs/ROLE_OS_2_ARCHITECTURE_PROPOSAL.md`'s "Router surface" finding ("too many parallel entry points for a 'simple' system"). This is an **analysis task first** — do not perform the actual navigation cleanup until the analysis is reviewed.

## After That

Known remaining Phase 1 work, in order:

1. **Task 8** — Navigation Simplification Analysis (see above)
2. **Task 9** — Discovery Report Artifacts: decide whether `var/discovery_reports/documents/` gets a real consumer or is removed
3. **Phase 1 validation** — a full-suite regression pass and a final canonical-runtime smoke test across everything Phase 1 touched
4. **Phase 1 completion report** — a single summary closing out Phase 1 before any Phase 2 planning begins

## Blocked / Requires Role Decision

- `var/role_os_alpha/`'s disposition (merge, archive, or discard) — see `CURRENT_STATE.md`'s Open Issues and `docs/RUNTIME_DATA_MAP.md`
- `var/discovery_reports/documents/`'s fate (Task 9 needs this decided, or needs to make the recommendation itself)
- Whether `role-content-factory`/`subir-libros-etsy` should ever be brought into Role OS's Discovery scope
- ROLE MASTER's status mismatch (legacy "Completado" vs. canonical "active") — cosmetic, no urgency, but unresolved

## Do Not Do Yet

- Do not migrate, merge, or delete `var/role_os_alpha/` without an explicit Role decision.
- Do not begin Phase 2 (or any work beyond the Phase 1 task list above) before Phase 1's validation and completion report.
- Do not delete or rewrite historical docs (`docs/PHASE_1_TASK_*.md`, `audits/`, `docs/product/DECISIONS.md`, `docs/architecture/01`–`21`) — they are frozen record, not living documentation.
- Do not treat `samples/role_os_sample/` as a production runtime source for anything — it is fixture/demo data only, reachable only via explicit `ROLE_OS_WORKSPACE_DIR`/`ROLE_OS_*_DB_PATH` selection.
- Do not perform the Task 8 navigation cleanup itself until its analysis has been reviewed — Task 8 as scoped above is analysis-only.
