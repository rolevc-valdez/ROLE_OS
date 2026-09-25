# Role OS 2.0 — Next Actions

*This file describes NEXT. It is overwritten at every completed major task, not appended to. It is a short queue, not a roadmap — see `docs/ROLE_OS_2_PHASE_2_PLAN.md` for Phase 2's full task list and reasoning.*

## Now

**Primary next action (the only one): finish Phase 3 — Task P3.6 — Daily Use Validation & Real Work Onboarding. IN PROGRESS — WAITING FOR REAL KONTOOR ITEMS.**

Done: bolsa-de-trabajo adopted; yt-dlp onboarded as a tool; P3.6B Daily Command Center polish (test data removed + test guard, misattributed snapshot invalidated, rescan, next-action honesty, differentiating Why, Where I Left Off moved up, Dashboard scroll/back, tool Open, "Daily Command Center" label). See `docs/PHASE_3_TASK_6_DAILY_USE_VALIDATION.md`.

**Role, please add (Workspace → Add External Work → Review → Save):**

1. **One real KONTOOR project that lives in Claude Web** — Name; Kind `project`; Domain `KONTOOR`; Source `Claude Web`; URL of the Claude project/conversation (if any); Status; Priority; Purpose/notes; Next action.
2. **One real KONTOOR reusable script/bookmarklet/tool** — Name; Kind `tool`; Domain `KONTOOR`; Source that matches reality (`Chrome bookmark` / `Claude Web` / `Web` / `Other`); URL if it has a normal http(s) link, otherwise a Reference saying where it lives; Status; Priority; Purpose/notes. Never paste bookmarklet code or credentials.

Then: final P3.6 validation (30-second test with KONTOOR data) and close P3.6. Windows startup only after that.

**Role decisions pending (not tasks):** the second, unlinked "ROLE Commerce Factory" PI project shown in Needs Attention (keep, merge or remove?); the newly discovered, un-adopted `KONTOOR` and `FERREVOLT` folders under `1 - IA PROJECTS` (adopt later or leave).

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
