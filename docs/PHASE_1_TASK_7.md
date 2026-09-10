# Role OS 2.0 — Phase 1 Task 7

## Objective

Establish a small, human-readable Markdown control layer whose sole purpose is continuity — so that after a lost session, a reboot, or a switch between AI assistants, a human or an AI can read a very small number of files and know where things stand, without re-deriving it from git history or task reports.

## Control Files Created

`CURRENT_STATE.md` and `NEXT_ACTIONS.md`, both at the repository root — exactly the two files the brief asked for, nothing more. Both are designed to be read in under two minutes.

## Source-of-Truth Boundaries

Made explicit (and documented in `CONTRIBUTING.md`'s new section, so it isn't only implicit in these two files' own headers):

| Kind of truth | Where it lives |
|---|---|
| Runtime/project truth | SQLite databases under `var/`, read via the application's own services |
| Current development state | `CURRENT_STATE.md` |
| Immediate development queue | `NEXT_ACTIONS.md` |
| Historical implementation detail | `docs/PHASE_1_TASK_*.md` |
| Architectural/product decisions | `docs/product/DECISIONS.md` |
| Code/change history | Git |

Neither control file inventories a database's full contents — `CURRENT_STATE.md` names the 5 canonical projects as a short list and links to `docs/RUNTIME_DATA_MAP.md` for anything more detailed, rather than re-deriving or duplicating that document's own findings.

## CURRENT_STATE.md Design

Sections: Status (phase/current task/last completed task+commit/overall state), What Is Working (concise bullets, one per major established capability from Tasks 1–6), Current Runtime Model (the two canonical roots, `var/role_os/` and `var/role_os_dashboard/`, with a pointer to `docs/RUNTIME_DATA_MAP.md` rather than re-inventorying it), Canonical Projects (the 5 real adopted projects, named explicitly so a reader never has to guess whether `samples/` or `var/role_os_alpha/` might be "the real list"), Open Issues / Decisions (only genuinely unresolved items, cross-checked against every prior task doc — see below), and Recovery (the exact minimal procedure, ending in an explicit "do not repeat completed tasks" instruction).

## NEXT_ACTIONS.md Design

Sections: Now (exactly one task — Task 8, with its objective in a few lines and an explicit "analysis first" guardrail), After That (the known remaining Phase 1 queue: Task 8 → Task 9 → Phase 1 validation → Phase 1 completion report), Blocked / Requires Role Decision (only items that are genuinely Role's call, not routine implementation work), and Do Not Do Yet (concise guardrails, including "do not begin Phase 2" and "do not treat samples as production runtime").

## Update Rules

Added a new section to `CONTRIBUTING.md` (chosen over a new standalone doc — it is already the repository's home for contributor-facing conventions) with the eight rules from the brief: overwritten-not-appended, phase-vs-task-report separation, decisions belong in `DECISIONS.md`, git is authoritative history, runtime DBs remain authoritative for runtime data, no full-database duplication into Markdown, and refresh-both-files-at-every-completed-task.

## Crash Recovery Test

Performed for real, using only `CURRENT_STATE.md`, `NEXT_ACTIONS.md`, `git status`, and `git log -5` (not from memory of this conversation):

| Question | Answer found | Consistent with git? |
|---|---|---|
| What phase are we in? | Role OS 2.0, Phase 1 (Core Consolidation) | — |
| Last completed task? | Task 6: Legacy Dashboard Preservation | — |
| Its commit? | `4d4a224` | **Yes** — matches `git log -5`'s HEAD exactly |
| Next task? | Task 8: Navigation Simplification Analysis | — |
| Tasks that must not be repeated? | All of Tasks 1–6 (per "What Is Working"); Task 8's actual cleanup work must not start before its analysis is reviewed | — |
| Open risks/decisions? | The 6 items in Open Issues / Decisions | — |
| Canonical runtime data location? | `var/role_os/` (Knowledge family, real data external at `ROLE_KNOWLEDGE_OS`) + `var/role_os_dashboard/` (Workspace/Session family, real 5 projects + 7 registry rows) | — |

**Result: PASS.** All seven questions answerable confidently from the two files alone, and the one directly git-checkable fact (the last commit hash) matched exactly.

## AI Handoff Test

Evaluated (not automated, per the brief — this establishes the contract, not tooling around it): a fresh session given only "Read CURRENT_STATE.md and NEXT_ACTIONS.md and continue Role OS 2.0" would find a named, scoped next task (Task 8) with its objective stated in the file itself, an explicit boundary on what NOT to do yet, and enough of the Open Issues list to avoid re-litigating already-settled questions (e.g., it would not need to re-discover that `var/role_os_alpha/` is ambiguous — that's already flagged). **Result: PASS.**

## Validation

- Both files exist at the repository root.
- Required headings present in both (verified by direct read, matching the brief's recommended structure).
- Every path referenced (`docs/RUNTIME_DATA_MAP.md`, `docs/PHASE_1_TASK_*.md`, `docs/product/DECISIONS.md`, `docs/ROLE_OS_2_ARCHITECTURE_PROPOSAL.md`) exists.
- The stated last completed commit (`4d4a224`) matches `git log`'s actual HEAD.
- The stated next task (Task 8: Navigation Simplification Analysis) matches the task sequence this conversation's own instructions have followed task-by-task (no task list was invented; it was read off the running sequence: Tasks 1–6 completed, this brief itself names Task 8 as next).
- No task listed as completed in `CURRENT_STATE.md` is also listed as pending in `NEXT_ACTIONS.md`, and vice versa.
- No sample (`samples/role_os_sample/`) or `role_os_alpha` path is described as canonical runtime anywhere in either file — both are named only in the Open Issues / Do Not Do Yet sections, explicitly as non-canonical.

No application code changed in this task, so no application-code tests were added, per the brief's own instruction not to invent test machinery for two Markdown files.

## Files Changed

- `CURRENT_STATE.md` — new
- `NEXT_ACTIONS.md` — new
- `CONTRIBUTING.md` — new "Keeping CURRENT_STATE.md and NEXT_ACTIONS.md current" section
- `docs/PHASE_1_TASK_7.md` — new

## Known Limitations

- These files describe the state as of Task 6's completion; they must be refreshed at the end of Task 8 (per the new `CONTRIBUTING.md` rule) or they will themselves become the next thing to drift.
- The Open Issues list was compiled from every prior task doc's own findings; it is only as complete as those docs — if a future task discovers a new unresolved item, it should be added here (by overwriting, not appending) at that task's completion, not retroactively invented now.

## Exact Next Task

Phase 1 — Task 8: Navigation Simplification Analysis
