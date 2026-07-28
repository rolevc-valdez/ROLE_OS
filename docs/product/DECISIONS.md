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

---

## Sprint 5's Knowledge Graph is a second, independent graph — not an extension of Epic 3's

**Decision**: `dashboard/app/conversation_graph/` is a standalone graph
domain with its own vocabulary (8 lowercase node types, one `contains`
relationship), its own API (`/conversation-graph`), and its own UI page —
computed from the imports/extraction databases. It does not extend
`app/graph/`'s `NODE_TYPES`/`RELATIONSHIP_TYPES`, does not add a builder
to `app/graph/builders/`, and does not share node ids with Epic 3's graph
even where a type name is the same (e.g. both have a "Person" concept,
but they're different nodes from different pipelines).

**Why**: Epic 3's graph vocabulary is frozen and test-locked —
`dashboard/tests/test_graph_api.py` asserts `GET /graph/meta/types`
returns exactly 12 node types and 12 relationship types, and three
architecture docs document "12 node types / 12 relationship types" as a
fixed fact (see [[../architecture/04_DATA_MODEL]]). Sprint 5 needed three
node types Epic 3 doesn't have (`Task`, `Idea`, `Document`) and a
relationship type it doesn't have (`contains`); adding them would have
broken a currently-passing test and contradicted the documented
"12/12" vocabulary. Beyond the test, the two graphs' overlapping type
names describe genuinely different things: Epic 3's `Conversation` nodes
come from the Builder's `knowledge_cards`; Sprint 5's `conversation` nodes
come from the imports database. Merging them under one id scheme risked
silently conflating two unrelated pipelines' data the first time a name
collided (e.g. two different `Person` slugs computed differently by each
pipeline landing on the same node, silently merging unrelated context).

**How to apply**: Don't extend Epic 3's `NODE_TYPES`/`RELATIONSHIP_TYPES`
tuples to accommodate a new feature unless that feature's data genuinely
belongs to the same three source databases (Builder, Project
Intelligence, Advisor) Epic 3 already reads. A new pipeline with its own
data source is a case for its own small graph domain, following this same
"compute layer, not a database" pattern (see the entry above) at whatever
smaller scale that pipeline needs — not a case for growing Epic 3's
vocabulary or reusing its id scheme.

---

## Sprint 6's Advisor Search is a sibling module inside `app/advisor/`, not a merge into the recommendation engine

**Decision**: Keyword search over conversations/extracted objects lives
in two new files, `app/advisor/search.py` and
`app/advisor/search_models.py`, registered through a **separate** FastAPI
router (`routers/advisor_search.py`) that happens to share the
`/advisor` URL prefix. Epic 2's recommendation engine — `db.py`,
`engine.py`, `rules/`, `scoring.py`, `narrative.py`, and
`routers/advisor.py` — is not modified, and search results are not
folded into `Recommendation` objects or the Daily Brief.

**Why**: "What should I work on next?" (Epic 2 — rule-based scoring over
Project Intelligence data, persisted dismiss/complete state) and "where
is everything about X?" (Sprint 6 — stateless keyword search over
imported conversations and extracted objects) are different questions
with different data sources and no shared logic; there was nothing to
gain from merging their code. But unlike the Sprint 5 Knowledge Graph
decision above, there was also no *test-locked vocabulary* or *identity-
collision* risk forcing a fully separate top-level domain — search has no
fixed type count to violate and no id scheme that could collide with
Epic 2's. So the answer here isn't "merge" or "fully separate," it's
"sibling": new files alongside the existing ones, under the same
conceptual umbrella (the Advisor page now does two related but distinct
things), registered as a second router so the diff to Epic 2's existing,
already-tested router is exactly zero lines.

**How to apply**: When a new capability is conceptually part of an
existing feature area but has its own data source and no logic to share,
prefer adding sibling files/routers within that area's package over
either (a) editing the existing files to accommodate the new logic, or
(b) spinning up a whole new top-level domain out of caution. Reserve (b)
for cases like the Sprint 5 entry above, where a shared vocabulary or id
scheme would create real collision risk.

## Where to go next

- [[../architecture/01_VISION]] and [[../architecture/02_PRINCIPLES]] — the
  standing principles these decisions are instances of.
- [[CHANGELOG_PRODUCT]] — the product-facing history these decisions shaped.
