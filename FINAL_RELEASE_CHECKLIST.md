# Final Release Checklist — ROLE OS v1.0

Verification performed as part of Sprint 9 (Release), 2026-07-28.

- [x] **Tests pass** — full repo-wide suite (`tests/`, `dashboard/tests/`,
      `builder/tests/`): **416/416 passed** (`python -m pytest` from the
      repo root).
- [x] **No credentials** — searched all tracked, non-Markdown files for
      `api_key`/`secret`/`password`/`token`/private-key markers; no
      matches beyond a `.gitignore` pattern entry (`.streamlit/secrets.toml`,
      itself just an ignore rule, not a secret).
- [x] **No generated files staged** — `.pytest_cache/`, `__pycache__/`,
      and `var/` (the Alpha demo's runtime SQLite databases) are all
      `.gitignore`d and confirmed untracked (`git ls-files` returns
      nothing under any of them).
- [x] **No cache directories tracked** — confirmed via `git ls-files`
      (no `__pycache__`, `.pytest_cache`, or `.DS_Store` entries).
- [x] **README complete** — root `README.md` covers what ROLE OS is,
      Features, Architecture overview, Screenshots placeholders,
      Requirements, Installation, Running locally, Repository structure,
      and License, per this release's documentation scope.
- [x] **Documentation complete** — `QUICK_START.md`, `INSTALLATION.md`,
      `ARCHITECTURE.md`, `CHANGELOG.md` (Sprint 8 and Sprint 9 entries
      added, `[Unreleased]` promoted to `[1.0.0]`), `RELEASE_NOTES_v1.0.md`,
      `LICENSE.md`, `CONTRIBUTING.md`, and this checklist all present at
      the repo root; `dashboard/README.md` updated to cover the
      previously-undocumented Settings domain (Sprint 8).
- [x] **Git clean** — `git status` shows only this release's intended
      changes staged (documentation, the Sprint 8 Settings code that had
      not yet been committed, and the version bump); no stray or
      unexpected files.
- [x] **Version updated** — `dashboard/app/config.py` (`app_version`) and
      `pyproject.toml` (`version`) both bumped from `1.0.0-alpha` /
      `0.1.0` to `1.0.0`.
- [x] **Release tag ready** — repository is in a committed, pushed state
      on `main` suitable for tagging `v1.0.0` (tag creation is a
      repository-owner action, not performed automatically by this
      checklist).

## What this checklist intentionally does not cover

- Real screenshots — still a documented placeholder (`docs/screenshots/`),
  not a release blocker per `RELEASE_NOTES_v1.0.md`.
- CI pipeline status — this repository does not currently have a CI
  workflow configured; verification here was performed locally.
- Multi-environment testing — verified on the local development
  environment only (Windows, Python 3.x via the project's `.venv`).
