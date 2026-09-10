# Contributing

ROLE OS is a proprietary, personal project (see
[`LICENSE.md`](LICENSE.md): **Proprietary – All Rights Reserved**). It is
not currently open to public contributions, and there is no public issue
tracker or pull-request process set up for outside contributors.

This file exists to document the conventions the codebase itself already
follows, for anyone with authorized access working on it.

## Development conventions already in use

- **Additive, non-breaking evolution.** Every sprint/epic documented in
  [`CHANGELOG.md`](CHANGELOG.md) has been layered on top of the previous
  one's API surface without modifying or removing it, confirmed by a
  regression test in that entry's own test suite. New work should follow
  the same pattern: prefer a new, namespaced router/domain over changing
  an existing endpoint's contract.
- **No external AI/LLM API calls.** Every extractor, health signal,
  Advisor rule, and graph relationship is rule-based and deterministic —
  see [`docs/architecture/01_VISION.md`](docs/architecture/01_VISION.md)
  for why this is a non-negotiable constraint, not a temporary limitation.
- **No data duplication.** Domains that derive information from another
  domain's database (the Advisor, both Knowledge Graphs) recompute on
  every read rather than maintaining their own copy.
- **Tests accompany every change.** Run the full suite from the repo root
  before proposing or merging anything:

  ```bash
  pip install -r requirements.txt
  python -m pytest
  ```

- **Documentation is part of the change.** When a domain's behavior
  changes, its section in `dashboard/README.md` (or `builder/README.md`)
  and the relevant `docs/architecture/*` file are updated in the same
  change, not deferred — Sprint 9 of this repository's history exists
  specifically because a prior sprint (Settings, Sprint 8) shipped code
  without its documentation, and that gap had to be closed before release.

## Keeping `CURRENT_STATE.md` and `NEXT_ACTIONS.md` current

Role OS 2.0 (Phase 1 Task 7) added two small root-level control files whose
job is continuity across a lost session, a reboot, or a switch between AI
assistants — not a second source of truth. Their rules:

1. `CURRENT_STATE.md` describes **now**. `NEXT_ACTIONS.md` describes
   **next**. Neither describes history.
2. Both are **overwritten to reflect current state**, never appended to —
   they are living files, not journals. If you find yourself adding a new
   dated entry instead of replacing a stale one, stop and rewrite instead.
3. Completed-task implementation detail belongs in `docs/PHASE_1_TASK_*.md`
   (or the equivalent for later phases), not in these two files.
4. Architectural/product decisions belong in `docs/product/DECISIONS.md`,
   not here.
5. Git is the authoritative change history — these files summarize the
   *current* consequence of that history, they don't replace `git log`.
6. Runtime/project data (SQLite databases under `var/`) remains the
   authoritative source for runtime and project state. These files may
   *describe* that data (e.g. "5 adopted projects") but must never become
   a second, drifting copy of it — see `docs/RUNTIME_DATA_MAP.md` for the
   actual inventory.
7. Do not duplicate an entire database's contents into Markdown. A short,
   named list (like the 5 canonical projects) is fine; a full dump is not.
8. **Refresh both files at the end of every completed major task, before
   committing** — update `CURRENT_STATE.md`'s Status/What Is
   Working/Open Issues and `NEXT_ACTIONS.md`'s Now/After That sections to
   match what just happened, in the same commit as the task's own work.

## Code style

- `black` (line length 100) and `ruff` (line length 100, target `py310`)
  are configured in `pyproject.toml`.
- Follow the existing per-domain module layout described in
  [`ARCHITECTURE.md`](ARCHITECTURE.md) and
  [`docs/architecture/06_DEVELOPMENT_RULES.md`](docs/architecture/06_DEVELOPMENT_RULES.md)
  rather than introducing a new organizing pattern.

## Reporting issues

See [`RELEASE_NOTES_v1.0.md`](RELEASE_NOTES_v1.0.md#bug-reporting).
