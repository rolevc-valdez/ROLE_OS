# Role OS 2.0 — Next Actions

*This file describes NEXT. It is overwritten at every completed major task, not appended to. It is a short queue, not a roadmap — see `docs/ROLE_OS_2_ARCHITECTURE_PROPOSAL.md` for the longer-range picture.*

## Now

**Phase 1 — Task 8B: Navigation Simplification Implementation**

Task 8's analysis (`docs/PHASE_1_TASK_8_NAVIGATION_ANALYSIS.md`) recommended implementation as **A — SMALL AND SAFE**: regroup the sidebar in `dashboard/app/templates/index.html`/`app.js` into a handful of clusters (Mission Control, Projects, Knowledge, Session, Settings), demote `/dashboard` (v2) from a top-level item to a "See full metrics →" link from Mission Control, and give the already-orphaned-from-nav Import/Extraction pages a home under Settings. **Zero routers, endpoints, services, or database schemas change** — this is a frontend information-architecture change only, and every existing deep link/hash route must keep working exactly as-is.

## After That

Known remaining Phase 1 work, in order:

1. **Task 8B** — Navigation Simplification Implementation (see above)
2. **Task 9** — Discovery Report Artifacts: decide whether `var/discovery_reports/documents/` gets a real consumer or is removed
3. **Phase 1 validation** — a full-suite regression pass and a final canonical-runtime smoke test across everything Phase 1 touched
4. **Phase 1 completion report** — a single summary closing out Phase 1 before any Phase 2 planning begins

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
- Do not remove, rename, or change the route path of any router during Task 8B — the analysis found zero routers worth removing; 8B is a sidebar/grouping change only.
