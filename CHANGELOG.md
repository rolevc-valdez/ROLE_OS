# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Added

- Milestone 3: Knowledge Engine 2.0 — a modular knowledge extraction
  pipeline under `builder/extractors/` that enriches every Knowledge Card.
  - New extractors, one responsibility each: `summary.py`, `decisions.py`
    (decisions + deliverables), `todos.py`, `prompts.py`, `entities.py`
    (people, applications, vendors, urls, files, project/tag
    classification), `relationships.py` (related conversations).
  - `extractors/__init__.py` defines the extended `KnowledgeCard` and
    `build_knowledge_card()`, which merges every extractor's output into
    one card.
  - New fields on every Knowledge Card: real `vendors` extraction
    (previously always empty), `files` (previously only exposed via the
    `assets` alias, which is kept for backward compatibility), and
    `related_conversations` — computed in a second, corpus-level pass
    (`attach_related_conversations`) via weighted overlap of project, tags,
    people, and applications across all cards.
  - New `VENDORS.json` cross-reference index alongside the existing
    PROJECTS/PEOPLE/APPLICATIONS/TAGS/TIMELINE indexes.
  - `builder.py`'s SQLite write (`role_os.db`) now happens after the
    relationship pass, so `related_conversations` and real `vendors` are
    persisted automatically.
  - `knowledge_extractor.py` is now a thin backward-compatible wrapper
    (`build_card`) around `extractors.build_knowledge_card` — the builder
    CLI, its arguments, and its output folder layout are unchanged.
  - No dashboard changes were required: the existing `/knowledge/{id}`
    endpoint already passes new fields through (`extra="allow"`).
  - New regression tests under `builder/tests/`: per-extractor unit tests,
    pipeline tests (including a backward-compatibility check that
    `knowledge_extractor.build_card` matches `extractors.build_knowledge_card`),
    and an end-to-end integration test asserting enriched output and
    updated SQLite.
  - Regenerated `samples/role_os_sample` with the new pipeline.

- Milestone 2: first usable ROLE OS web dashboard, served directly by the
  existing FastAPI app at `/`. Built with plain HTML, CSS, and JavaScript —
  no frontend framework.
  - Global search bar (uses the existing `GET /search?q=` endpoint).
  - Project list with conversation counts (uses the existing `GET /projects`
    endpoint); clicking a project filters the card list.
  - Recent knowledge cards list (new additive `GET /ui/recent` endpoint).
  - Knowledge card detail view/modal showing summary, decisions,
    deliverables, to-dos, people, applications, and tags (uses the existing
    `GET /knowledge/{id}` endpoint).
  - Basic chronological timeline (new additive `GET /ui/timeline` endpoint).
  - The four Milestone 1 API endpoints (`/health`, `/projects`, `/search`,
    `/knowledge/{id}`) are unchanged; `/ui/recent` and `/ui/timeline` are
    additive, UI-only endpoints and do not alter existing API contracts.
  - UI tests (`dashboard/tests/test_ui.py`) covering page rendering, static
    asset serving, the new `/ui/*` endpoints, and a regression check that
    the original API responses are unaffected.

- Repository project structure: `/builder`, `/dashboard`, `/docs`, `/tests`,
  `/scripts`, `/samples`.
- Migrated the existing ROLE OS Builder (`builder.py`,
  `knowledge_extractor.py`, `run_windows.bat`) into `/builder`, unchanged
  functionally, with an updated README and `requirements.txt`.
- New FastAPI dashboard application under `/dashboard` exposing:
  - `GET /health`
  - `GET /projects`
  - `GET /search?q=`
  - `GET /knowledge/{id}`
  Backed by the SQLite database produced by the builder. No AI features.
- Sample ChatGPT export and generated ROLE Knowledge OS output under
  `/samples` for local smoke-testing.
- Repo-level and dashboard-level test suites (pytest).
- Root `README.md`, `pyproject.toml`, and `.gitignore` additions.
