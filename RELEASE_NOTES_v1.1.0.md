# ROLE OS — Release Notes v1.1.0

**Release date:** 2026-07-30
**Previous version:** 1.0.0 (2026-07-28)
**Release type:** Minor (backward-compatible new feature, per `standards/VERSIONING.md`)

## Summary

v1.1.0 adds the **ROLE OS Dashboard MVP: Daily Session** — a Start/End My
Day workflow that turns the ROLE OS Framework's operating methodology
(session modes, project and decision discipline) into a real, working part
of the product. This release is entirely additive: every endpoint, page,
and database that existed in v1.0.0 is unchanged.

## New features

- **Daily Session domain** (`dashboard/app/session/`) — a new, self-owned
  SQLite-backed domain for starting and closing a work session.
- **Six operation modes** (PLAN, BUILD, CREATE, LAUNCH, OPERATE, LEARN),
  each with a name, purpose, expected AI behavior, and primary ROLE
  Ecosystem resources — defined once (`app/session/modes.py`) and served
  to the UI, not duplicated.
- **Start My Day** — a form (date, project, mode, objective, expected
  result, optional notes) that opens a session; only one session may be
  active at a time.
- **Claude session prompt generator** — produces the exact, copyable
  `Initialize using SYSTEM.md...` prompt structure for starting an AI
  collaboration session.
- **End My Day** — closes the active session, recording completed work,
  decisions made, blockers, and the next step.
- **Obsidian-compatible daily Markdown record** — generated in the exact
  required `# YYYY-MM-DD` / `## Project` / `## Mode` / ... format; can be
  copied, downloaded as a `.md` file, or optionally written directly into
  a configured Obsidian vault folder.
- **Local project registry** — seeded with ROLE OS, ROLE ECOSYSTEM, ROLE
  MASTER, ROLE Commerce Factory, Brand Character OS, RoleValdez, and
  SUPER FACIL; editable inline, with real (not placeholder) status for
  every project where the ROLE Ecosystem's own documentation already
  states it.
- **Recent ecosystem decisions** — reads `role-ecosystem/DECISION_LOG.md`
  live when configured, with a documented, explicitly-labeled fallback
  otherwise; never duplicates the full log.
- **New sidebar page**: **Session** (`#/session`), built as its own page
  rather than folded into the existing Home page (see
  `docs/product/DECISIONS.md`).

## Improvements

- **Dark and light theme support** added to the entire Command Center
  (`app/static/css/colors.css`), not just the new Session page — a
  `@media (prefers-color-scheme: light)` override block re-themes every
  existing page for free, since all styling already routes through CSS
  custom properties.
- Form input styling (`input[type="date"]`, `textarea:focus`) extended
  in `components.css` to support the new Start/End My Day forms.

## Technical changes

- Three new `Settings` fields in `app/config.py`: `session_db_path`
  (`ROLE_OS_SESSION_DB_PATH`), `obsidian_daily_notes_dir`
  (`ROLE_OS_OBSIDIAN_DAILY_NOTES_DIR`), `ecosystem_decision_log_path`
  (`ROLE_OS_ECOSYSTEM_DECISION_LOG_PATH`) — all optional, all env-var
  driven, none hardcoded.
- New router `dashboard/app/routers/session.py`, namespaced under
  `/session`, registered additively in `app/main.py`.
- `session_db_path` defaults under the git-ignored `var/` directory
  rather than `samples/`, since session data is real personal data, not
  a checked-in fixture.
- No AI/LLM API call anywhere in the new code — the Claude prompt and the
  Markdown record are pure string templating over user-entered data,
  consistent with every other domain in ROLE OS.
- Version bumped: `pyproject.toml` and `dashboard/app/config.py`
  (`app_version`), `1.0.0` → `1.1.0`.

## Tests performed

- Full automated suite: **464 passed, 0 failed** (416 pre-existing + 48
  new for the Session domain), re-confirmed clean after the version bump.
- `ruff check`: clean (one pre-existing, repo-wide `Depends()`-in-default
  pattern common to every router, not introduced by this release).
- `black --check`: clean.
- **Live smoke test** against a real running server: start a session →
  fetch the Claude prompt → close the session → fetch and download the
  Markdown record → confirmed exact required format for both.
- **Persistence test**: killed the running server process and started a
  fresh one against the same SQLite file — the completed session and a
  registry edit were both still present.
- **Live decisions adapter test**: configured
  `ROLE_OS_ECOSYSTEM_DECISION_LOG_PATH` against the real
  `role-ecosystem/DECISION_LOG.md` and confirmed a correct live parse
  (verified at the raw HTTP-byte level, including non-ASCII characters).

## Compatibility

- **Fully backward compatible.** No existing endpoint's request/response
  contract changed; no existing database was touched; no existing page's
  markup or behavior changed.
- Requires the same Python 3.10+ and `dashboard/requirements.txt` as
  v1.0.0 — no new dependency was added.
- Upgrading from v1.0.0 requires no data migration: the new
  `role_os_session.db` is created automatically on first use.

## Known limitations

- The Daily Session domain has no CI wiring beyond what the repository
  already runs manually (`python -m pytest`) — unchanged from v1.0.0's
  overall CI posture.
- Registry editing is per-field inline forms, not a dedicated modal.
- `role-ecosystem/projects/ROLE_OS.md` and this repository's own
  documentation were reconciled as part of preparing this release
  (see `DECISION_LOG.md` entry `D-006` in `role-ecosystem`), but ROLE OS
  still has no entry in `role-ecosystem/business/` — it remains an
  internal tool without a defined commercial path.
- As with v1.0.0: single-user, single-machine, no authentication, no
  external AI/LLM integration anywhere in the system.

## Next milestone: v1.2 — Intelligent Session

Not started as part of this release (see `role-ecosystem/PRODUCT_LIFECYCLE.md`
— this release closes Build/Release for v1.1.0 before any new feature work
begins). Candidate scope for v1.2, to be scoped properly in its own PLAN
session:

- Wire each mode's `resources` list (already generated, not yet surfaced)
  into the Claude prompt's "Read only the documentation required for this
  mode and project" line, so the prompt names the actual files to read.
- Auto-suggest an objective/expected result from the project registry's
  `milestone`/`next_action` fields when starting a session.
- Session history browsing (`GET /session/recent` already exists; no UI
  consumes it yet).

## Bug reporting

See `RELEASE_NOTES_v1.0.md`'s Bug reporting section — the process is
unchanged for this release.
