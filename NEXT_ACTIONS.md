# Role OS 2.0 — Next Actions

*This file describes NEXT. It is overwritten at every completed major task, not appended to. It is a short queue, not a roadmap — see `docs/ROLE_OS_2_PHASE_2_PLAN.md` for Phase 2's full task list and reasoning.*

## Now

**Primary next action (the only one): Phase 3 — Task P3.7 — Windows Startup & Daily Launch.**

**NOT STARTED. Requires Role's go-ahead.** Goal: make Role OS easy to launch automatically when Role signs into Windows, reusing the existing launcher (`Start ROLE OS.bat` / `scripts/Start-RoleOS.ps1`, which already health-checks and avoids duplicate servers) and the stable Daily Command Center. No background services unless genuinely necessary. Worth considering in its scope: refreshing the Workspace scan at daily launch (discovery freshness goes stale 24 h after a scan).

Status: Phase 2 COMPLETE (`20b80df`); Phase 3 IN PROGRESS — P3.1–P3.6 COMPLETE (P3.6: `docs/PHASE_3_TASK_6_DAILY_USE_VALIDATION.md`). Phase 3 core product goal: PASS. Do not repeat them. Phase 3 closes after P3.7.

**Non-blocking backlog (from P3.6, not tasks until Role picks them):** Where I Left Off can pick a freshly added item over real last work; completed-project detail still offers Resume Work first; "No projects in this domain." wording when a domain has only completed work/tools; duplicate unlinked "ROLE Commerce Factory" PI project; OI "open next action" wording; ROLE_KNOWLEDGE_OS looks active from Role OS's own DB writes; Dashboard v2 counts tools as projects; Advisor recommendations outlive deleted PI projects; no edit UI for external items; un-adopted FERREVOLT / KONTOOR folders.

## Blocked / Requires Role Decision (all DEFERRED, none approved)

- `var/role_os_alpha/`'s disposition — **DEFER**, per Role's explicit instruction. Do not modify, migrate, delete, rename, or reinterpret it during Phase 2 without separate authorization.
- Whether to actually set `ROLE_OS_DISCOVERY_ROOTS` in any real running configuration, which of the 6 real, un-adopted projects (5 of which are now confirmed discoverable once it is set) to include, and whether to adopt any of them — **DO NOT ADOPT YET**; Task 2.1 only built and validated the capability, it did not enable it or adopt anything.
- The Advisor vs. Operational Intelligence/Executive Decision overlap — **DEFER**; do not redesign or remove Advisor in Phase 2.
- `pi_ai_workspace` — review complete (`docs/PHASE_2_PI_AI_WORKSPACE_REVIEW.md`): Legacy + Current, recommended for future deprecation. **Deprecation marking and removal are both a separate, not-yet-approved task** — no action taken here beyond the analysis itself.
- ~~Explicit project registration mechanism~~ — **DONE in P3.4.** Adopting bolsa-de-trabajo, and registering any other project, remain Role's decisions.

## Do Not Do Yet

- Do not modify, migrate, delete, rename, or reinterpret `var/role_os_alpha/` under any circumstance without a separate, explicit Role authorization.
- Do not auto-adopt any of the 6 real projects outside the Discovery root, even after Multi-Root Discovery makes them visible.
- Do not redesign or remove Advisor.
- Do not remove, deprecate-mark, rename, or modify `pi_ai_workspace`/`ai_workspace` without a separate, explicit Role authorization — the review (`docs/PHASE_2_PI_AI_WORKSPACE_REVIEW.md`) recommends eventual deprecation but does not approve acting on it.
- Do not treat `samples/role_os_sample/` as a production runtime source for anything.
- Do not delete or rewrite historical docs (`docs/PHASE_1_TASK_*.md`, `docs/PHASE_1_COMPLETION.md`, `docs/PHASE_2_TASK_*.md`, `audits/`, `docs/product/DECISIONS.md`, `docs/architecture/01`–`21`).
- Do not start any speculative feature work; anything not chosen by Role during Phase 3 scoping stays deferred.
