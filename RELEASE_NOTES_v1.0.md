# ROLE OS — Release Notes v1.0

**Release date:** 2026-07-28

This is the first v1.0 release of ROLE OS: a personal Knowledge Operating
System built on top of your ChatGPT conversation history, with no external
AI/LLM API call anywhere in the system.

## Highlights

- **Builder** — an offline CLI that turns a ChatGPT conversations export
  into structured Knowledge Cards (summary, decisions, to-dos,
  deliverables, people, applications, vendors, tags, related
  conversations) and a SQLite database, with no third-party dependencies.
- **Project Intelligence** — first-class Workspaces, Projects,
  Capabilities, Dependencies, and a modular, explainable Health Score
  engine.
- **AI Advisor** — eight independent, deterministic rules recommend what
  to work on next, each with a `reason`, `evidence`, `suggested_action`,
  and `impact` — fully explainable, no black box, no external AI call.
- **Knowledge Graph** — two independent, computed-on-demand graphs (no
  dedicated graph database): a 12 node-type / 12 relationship-type graph
  over Projects/Advisor/Builder data, and a second, smaller graph over
  imported conversations and their extracted objects.
- **ChatGPT Conversation Importer + Conversation Explorer** — bring
  conversations in directly without regenerating the Builder output, then
  browse, search, filter, inspect, and manage them.
- **Knowledge Extraction** — deterministic, rule-based extraction of
  Projects, People, Tasks, Decisions, Ideas, Documents, and Assets from
  imported conversations.
- **Advisor Search** — keyword search across every imported conversation
  and extracted object, with direct links to the Conversation Explorer
  and Knowledge Graph.
- **Dashboard** — an executive-summary page with live counts, recent
  activity, and system status.
- **Settings** — a read-only, exportable view of configuration and live
  system status, plus maintenance actions (rebuild graph, clear cache).
- **Command Center UI** — one dark-themed, framework-free single-page app
  over all of the above, built with plain HTML/CSS/vanilla JS.

See [`CHANGELOG.md`](CHANGELOG.md) for the full sprint-by-sprint history.

## Known limitations

These are current, documented boundaries of the v1.0 scope — not defects.
See each domain's own "Known limitations" section in
[`dashboard/README.md`](dashboard/README.md) and
[`docs/product/CHANGELOG_PRODUCT.md`](docs/product/CHANGELOG_PRODUCT.md)
for full detail; summarized here:

- **No external AI/LLM integration.** Every extractor, health signal,
  Advisor rule, and graph relationship is rule-based, not model-based —
  this is a deliberate product decision for v1.0, not a gap.
- **Single-user, single-machine.** No authentication, no multi-user
  accounts, no remote deployment story — ROLE OS is designed to run
  locally against your own data.
- **Extraction is regex/keyword-based, not NLP.** It will miss
  decisions/tasks/ideas phrased outside known keyword patterns, and the
  Person detector can both miss real names and occasionally match a
  non-name phrase.
- **No cross-conversation identity resolution.** The same person or
  project mentioned in two different conversations is stored as two
  separate extracted objects, not merged into one.
- **Search is substring matching, not semantic search.** Advisor Search
  and the Conversation Explorer's search both do plain, case-insensitive
  substring matching — no fuzzy matching, no typo tolerance, no relevance
  ranking beyond recency.
- **Settings import is preview-only.** Uploading a configuration file
  shows which environment variables it maps to; it never applies them to
  the running process. There is no mechanism to safely mutate a live
  server's environment, by design.
- **Delete operations are permanent.** Deleting an imported conversation
  or an extracted object has no undo/trash — a confirmation dialog is the
  only safety net.
- **No background jobs or continuous sync.** Every import and extraction
  run is a one-shot, user-initiated action.
- **No screenshots bundled yet.** Placeholder locations are documented in
  `README.md`; run the app locally to see the live UI.

## Future roadmap (brief)

Documented extension seams exist for future work, without any current
commitment to a schedule — see
[`docs/architecture/07_ROADMAP.md`](docs/architecture/07_ROADMAP.md) for
detail:

- An `AdvisorNarrativeProvider` seam for a future LLM-backed narrative
  provider that could improve recommendation *wording* without touching
  the deterministic rule/scoring core.
- A headless Graph Query Engine (`dashboard/app/graph/queries.py`) usable
  by a future AI provider or script without going through the HTTP API.
- A `commits` Health Score signal that's implemented but has no data
  source yet (no git integration wired up).
- Real screenshots for the README and Command Center documentation.
- A keyboard-shortcut layer (every interaction today is click-driven).

## Bug reporting

This is a personal/proprietary project (see [`LICENSE.md`](LICENSE.md)).
If you encounter an issue while running ROLE OS locally:

1. Reproduce it with `python -m pytest` from the repo root to check
   whether it's a regression the test suite already catches.
2. Check `docs/product/DECISIONS.md` and each domain's "Known
   limitations" section in `dashboard/README.md` — it may be documented,
   expected behavior rather than a bug.
3. If it's a genuine defect, open an issue against the repository (if you
   have access) with: the command or UI action that triggered it, the
   full error/traceback, and your Python version (`python --version`).
