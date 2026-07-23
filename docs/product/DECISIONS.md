# Product Decisions

A running log of consequential product/architecture decisions and the
reasoning behind them, distinct from the changelog (which records *what*
shipped) — this records *why* it was built that way. Newest first.

---

## No external AI/LLM API is called anywhere in the system

**Decision**: Every extractor, Health Score signal, Advisor rule, and
Knowledge Graph relationship is deterministic and rule-based. No OpenAI,
Claude, or any other model API is called by the Builder or Dashboard.

**Why**: Determinism makes every output reproducible and fully
explainable — a recommendation or relationship can always be traced back
to the exact data that produced it, with no risk of hallucination, API
cost, latency, or a network dependency for a tool meant to run entirely
against local SQLite files. Explainability was treated as a core product
requirement for the Advisor specifically (Epic 2), not a nice-to-have.

**How to apply**: Any future feature that seems to call for "AI" should
first be checked against the existing deterministic toolkit
(`app/advisor/scoring.py`, the Health Score signals) — most "make this
smarter" asks can be served by a better rule or signal. Where an LLM
genuinely adds value (e.g. rephrasing a recommendation's wording), it
must go through the narrow `AdvisorNarrativeProvider` seam and must not
change *what* the deterministic core decides. See
[[../architecture/06_DEVELOPMENT_RULES]].

---

## The Knowledge Graph is a compute layer, not a fourth database

**Decision**: `build_graph()` recomputes the full graph from the Builder,
Project Intelligence, and (on demand) Advisor databases on every request,
rather than persisting graph state anywhere.

**Why**: A persisted graph would need to be kept in sync with three other
independently-mutated databases, creating a class of bugs (stale
relationships, drift between a project's real state and its graph
representation) that simply cannot occur if the graph is always freshly
derived. The same "recompute on read" pattern was already validated by
the Advisor in Epic 2, so Epic 3 reused it rather than introducing a new
consistency model.

**How to apply**: Prefer computing derived data on read over persisting a
copy, unless there's a demonstrated performance problem that recomputation
can't solve (there hasn't been one yet — see the Performance section of
[[../architecture/05_UI_GUIDELINES]] for how the UI avoids the N+1 pattern
that would otherwise make recompute-on-read expensive).

---

## Project Intelligence lives under `/pi`, not `/projects`

**Decision**: The existing `/projects` endpoint (a Milestone 1 knowledge-
API concept: conversation counts grouped by a classifier string) was left
untouched. First-class Project records got a new namespace, `/pi/*`,
entirely.

**Why**: `/projects` and a first-class "Project" record are genuinely
different concepts that happen to share a name. Reusing the endpoint would
have silently changed its meaning for existing consumers; a new namespace
avoided that ambiguity entirely rather than requiring a version bump or a
breaking migration.

**How to apply**: When a new concept's natural name collides with an
existing endpoint's name, prefer a new namespace over overloading the old
one — even if it means a slightly less intuitive URL. See
[[../architecture/02_PRINCIPLES]] §3.

---

## Epic 4 (Command Center) introduced zero backend changes

**Decision**: The entire dashboard UI redesign — new sidebar, hash router,
Home/Project/Graph/Advisor/Assets/Settings pages, and design system — was
built with no new API endpoint, database, or backend logic.

**Why**: Every piece of data the new UI needed already existed behind an
endpoint from Milestones 1–3 or Epics 1–3. Building it as a pure
presentation layer kept the backend's test coverage and behavior
completely stable through a large, highly visible change, and proved the
existing API surface was actually sufficient to power a real product UI —
a useful validation of the additive-namespacing decisions made in Epics
1–3.

**How to apply**: Before adding a backend endpoint for a UI feature,
confirm the data really isn't available through composition of existing
endpoints first. See [[../architecture/05_UI_GUIDELINES]].

---

## Builder has zero third-party dependencies

**Decision**: `builder/requirements.txt` intentionally stays empty of
third-party packages; the entire extraction pipeline is standard-library
Python.

**Why**: The Builder is meant to run as a simple, portable CLI (including
via `run_windows.bat` for non-technical use) against a user's own ChatGPT
export, with nothing to install and nothing that can break from a
dependency update or an unavailable package index.

**How to apply**: Adding a third-party dependency to the Builder should be
treated as a significant, deliberate decision requiring explicit
justification — not a default choice for convenience.

## Where to go next

- [[../architecture/01_VISION]] and [[../architecture/02_PRINCIPLES]] — the
  standing principles these decisions are instances of.
- [[CHANGELOG_PRODUCT]] — the product-facing history these decisions shaped.
