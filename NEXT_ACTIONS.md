# Role OS 2.0 — Next Actions

*This file describes NEXT. It is overwritten at every completed major task, not appended to. It is a short queue, not a roadmap — see `docs/ROLE_OS_2_PHASE_2_PLAN.md` for Phase 2's full task list and reasoning.*

## Now

**Nothing open.** Phase 2 is formally complete — see `docs/PHASE_2_COMPLETION.md` for the full closing-validation record (14 sections, all PASS) and `CURRENT_STATE.md` for the current-state summary.

A reported power loss interrupted the session before closing validation began; the next session confirmed (via `git log`, `git status`, and absence of `docs/PHASE_2_COMPLETION.md`) that no closing-validation work had actually started, then ran the full validation from scratch: git/repo health, canonical runtime paths, canonical data integrity (`PRAGMA integrity_check: ok` on all 8 DBs), the full 1,372-test suite (split `tests/` + `builder/tests/` + `dashboard/tests/` to avoid the earlier memory issue), SHA256/size/mtime of all canonical DBs before and after the suite (byte-identical — Test Isolation confirmed holding), Multi-Root Discovery re-verification (22 tests, deliberately left disabled), a live Mission Control smoke test, router/navigation regression (32 routers, 136 API paths), documentation validation, Runtime Data Hygiene re-verification, a crash-recovery test (this session's own recovery, per `CURRENT_STATE.md`'s Recovery procedure), an AI-handoff test, and the Phase 2 task resolution matrix (all 5 tasks, 2.1–2.5, confirmed DONE).

## After That

No Phase 3 task exists yet and none was scoped by the closing validation, per its explicit instruction not to begin Phase 3. Scoping Phase 3 is the next real piece of work, whenever Role is ready to start it.

## Blocked / Requires Role Decision

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
