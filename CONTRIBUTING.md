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

## Code style

- `black` (line length 100) and `ruff` (line length 100, target `py310`)
  are configured in `pyproject.toml`.
- Follow the existing per-domain module layout described in
  [`ARCHITECTURE.md`](ARCHITECTURE.md) and
  [`docs/architecture/06_DEVELOPMENT_RULES.md`](docs/architecture/06_DEVELOPMENT_RULES.md)
  rather than introducing a new organizing pattern.

## Reporting issues

See [`RELEASE_NOTES_v1.0.md`](RELEASE_NOTES_v1.0.md#bug-reporting).
