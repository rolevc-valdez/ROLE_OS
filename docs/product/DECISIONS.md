# Product Decisions

A running log of consequential product/architecture decisions and the
reasoning behind them, distinct from the changelog (which records *what*
shipped) — this records *why* it was built that way. Newest first.

---

## A formal Discovery Engine Domain Model was written before any persistence, identity resolution, or API work began

**Decision**: `docs/architecture/11_DISCOVERY_ENGINE_DOMAIN_MODEL.md`
(renumbered from an initial `10_` that collided with the unrelated,
already-uncommitted `10_WORKSPACE_ADOPTION_SPRINT2_REPORT.md`, left
untouched) defines 26 domain concepts (Workspace through Workspace Graph
Edge), their boundaries, invariants, lifecycles, a conceptual identity-
resolution model, a source-of-truth matrix, and a logical (not physical)
persistence/API boundary — with zero code, schema, or endpoint changes.
Several consequential decisions from that document (and its architectural
review) are recorded here:

1. **Discovered Project and Managed Project are, and will remain, separate
   concepts** — a Discovered Project is recomputed evidence, owned
   entirely by Discovery; a Managed Project is a human's curated decision,
   owned by Project Intelligence. Linking them (once Identity Resolution
   exists) creates a *reference* between two records that keep their own
   lifecycles — it never merges their schemas into one row, and discovered
   data may only ever fill a gap in a Managed Project, never overwrite a
   field a human already set.
2. **Identity resolution requires human confirmation in its initial
   implementation, regardless of confidence score.** Even "exact evidence"
   (matching git remote, matching path history) produces an Identity
   Candidate awaiting a Human Confirmation, not an automatic link. No
   confidence threshold promotes a candidate to confirmed on its own.
3. **Discovery owns its own persisted scan records** (a future
   `discovery_*` SQLite file, never `role_os_projects.db`), following the
   same "each domain owns its own database" convention already used by
   Projects, Advisor, Imports, and Extraction — not a new pattern, a
   continuation of an existing one.
4. **Discovery's Recommendation stays advisory, not an executable
   action**, matching how Advisor's `suggested_action` already works —
   nothing in Discovery, today or proposed, moves, renames, merges, or
   archives a folder in response to a Recommendation. Only a human,
   acting entirely outside Discovery's own read-only guarantee, ever
   performs the actual filesystem operation.
5. **A Recommendation's `action`/`reasons`/generated timestamp/rule-or-
   engine-version may be retained as part of a future persisted scan
   result or Snapshot** — but full recommendation *lifecycle* (dismiss,
   accept, snooze, a history UI) is explicitly deferred past Sprint 2, and
   is not the same commitment as Advisor's already-built
   persist-and-dismiss model. Recording the value is in scope; managing
   its lifecycle is not, yet.
6. **`Merge with another project` stays a reserved, valid action in the
   six-action vocabulary — not deleted, and not required to be emitted by
   any current rule.** No rule may emit it without strong identity *and*
   relationship evidence, and — like every other action — it never
   executes anything on its own; a human confirms it before any
   consolidation happens. It is documented in the Domain Model as
   reserved/inactive, not as a gap to silently paper over.
7. **The Projects domain is the sole authority for *confirmed* Project
   Relationships and Project Families.** Discovery may only produce
   *candidate* relationships from discovered evidence — labeled
   distinctly (`possible duplicate of`, `possible archived copy of`,
   `possible fork of`, `possible child module of`, `possible member of
   project family`, `possible successor/predecessor`) so a candidate is
   never mistaken for a confirmed fact. A Discovery candidate relationship
   becomes an authoritative one only through the same explicit Human
   Confirmation step Identity Resolution already requires (decision 2) —
   Discovery never silently creates or overwrites an authoritative
   relationship.
8. **Managed Project Health and Discovered Project Health remain two
   separate, separately-explainable scores — never silently merged into
   one number.** Managed Project Health evaluates the curated,
   human-maintained record (`projects/health/`, unchanged); Discovered
   Project Health evaluates technical/structural filesystem evidence
   (`discovery/health.py`, unchanged). Either may be *displayed* alongside
   the other once a link exists, but any future single composite score
   combining them must be its own explicitly-defined, explainable, and
   versioned computation — not an implicit average or a silent
   replacement of one by the other.

**Why**: Sprint 1/1.5 built a real, tested, read-only audit engine, but
its only formal vocabulary lived in code (`DiscoveredProject`'s ~50 flat
fields) and one architecture proposal that pre-dated the actual
implementation and used "Project" ambiguously for both discovered and
managed projects. Persistence, an API, and identity resolution were all
about to be designed next — and each of those would have had to invent
(or silently assume) this vocabulary under implementation pressure,
exactly the situation that produces terminology drift (three different
meanings of "Project" across three modules) and safety gaps (the kind of
"confidence score alone shouldn't merge two real projects" rule that's
easy to skip when it's not written down anywhere before the merge code
exists). Writing the domain model first, with no code attached, let this
get reviewed and challenged before it was load-bearing — decisions 5-8
above are exactly that review's output: each one closes a specific gap
(recommendation persistence scope, the unused `Merge` action, relationship
authority, and health-score conflation) the initial draft had left
implicit or only partially resolved.

**How to apply**: Before Sprint 2 (or any future Discovery work) adds a
table, endpoint, or algorithm, check it against
`11_DISCOVERY_ENGINE_DOMAIN_MODEL.md`'s vocabulary, invariants, and open
questions first — in particular: persisting a Recommendation's *value* is
fine in Sprint 2; building dismiss/accept/snooze is not, yet. Any rule
that emits `Merge with another project` needs both strong identity
evidence and human confirmation, no exceptions. Any Discovery-derived
relationship must be labeled as a candidate (`possible ...`) until a human
confirms it into the Projects domain. And any UI or scoring work touching
"health" must keep Managed and Discovered health visibly distinct unless
a new, explicit composite score has been separately designed and
versioned.

---

## Discovery Engine Sprint 1.5: detectors and recommendations moved to registry/rule-engine architecture, no product behavior changed

**Decision**: Sprint 1.5 was scoped as structural hardening only (no new
features, no persistence, no API). Three refactors:

1. **Detector registry** (`dashboard/app/discovery/detectors/`, replacing
   the single flat `detectors.py`): one shared, read-only `FolderInventory`
   walk (`inventory.py`) records raw structural facts only (which files/
   dirs exist, names, extensions) with zero interpretation; twelve
   independent detector modules (`documentation.py`, `testing.py`,
   `environment.py`, `scripts.py`, `docker.py`, `ci.py`, `databases.py`,
   `obsidian.py`, `vscode_workspace.py`, `markers.py`, `assets.py`,
   `absolute_paths.py`) each own a small `Findings` dataclass and a pure
   `detect(inventory) -> Findings` function; `registry.run_all()` merges
   them with a collision guard (`DetectorFieldCollisionError`) so two
   detectors can never silently claim the same `DiscoveredProject` field.
   This mirrors `app/projects/health/` and `app/advisor/rules/`'s existing
   "one signal, one file, one registry" shape — Discovery had reinvented a
   worse version of a pattern this codebase already solved.
2. **Recommendation rule engine** (`dashboard/app/discovery/recommendation/`,
   replacing the flat `recommendation.py`'s if/elif ladder): six rules
   (`rules/non_project.py`, `high_move_risk.py`, `brand_asset_project.py`,
   `documentation_project.py`, `real_project.py`, `fallback.py`), each an
   independent `evaluate(project) -> RecommendationCandidate | None` with
   an explicit `PRIORITY` int. `engine.recommend()` runs every rule and
   keeps the highest-priority candidate that fired — precedence is an
   inspectable number on each rule, documented in a table in
   `rules/__init__.py`, not implicit if/elif ordering. Verified (test:
   `test_rule_order_in_list_does_not_affect_precedence`) that reversing
   the rules' list order doesn't change any outcome.
3. **Pipeline-stage safety** (`dashboard/app/discovery/pipeline.py`, new,
   ~60 lines): a `PipelineStage` `IntEnum` (`NEW` → `DETECTED` →
   `CLASSIFIED` → `SCORED` → `RECOMMENDED`) stamped onto
   `DiscoveredProject.stage` as each stage completes, and a
   `require_stage()` guard called at the top of `health.compute_health()`
   (needs `CLASSIFIED`) and `recommendation.recommend()` (needs `SCORED`).
   Calling either out of order now raises `PipelineStageError` instead of
   silently scoring against incomplete/default data (e.g.
   `commercial_readiness == "unknown"` quietly mapping to a plausible-
   looking 20). This was the smallest safeguard that closed the gap, not a
   `DiscoveredProject` model rewrite — its shape is unchanged.

Behavioral parity was proven, not assumed: re-running the CLI against both
real corpora used in the Sprint 1 report (`Documents`, `1 - IA PROJECTS`)
produced byte-for-byte identical Markdown reports before/after the
refactor (the one line that differed was `ROLE_OS`'s own git commit hash,
which changed because of an unrelated checkpoint commit made between
runs — not a behavior change). Two known pre-existing quirks were
preserved deliberately rather than "fixed": `go.mod` files are still
double-counted in `tech_markers` (a Sprint 1 bug now documented in
`detectors/markers.py`, left alone because fixing it would silently change
`confidence_score` and possibly classification for Go projects), and
`DiscoveredProject.frameworks` is still always empty (never had a detector
in Sprint 1 either).

**Why**: The architecture review after Sprint 1 identified detectors.py's
single ~150-line `analyze_folder()` and recommendation.py's if/elif ladder
as the two places that would not scale as more detectors/rules were added
— every addition meant editing a shared function, with no isolation
between unrelated concerns and no way to test one detector without the
whole walk. Pipeline-stage safety closed a related but separate risk: nothing
enforced that `compute_health`/`recommend` were only ever called after
classification, which worked today only because `classifier.classify()`
happens to be the sole call site.

**How to apply**: A new Discovery Engine detector is a new file with a
`Findings` dataclass + `detect()` function, plus one line in
`detectors/registry.py::DETECTOR_REGISTRY` — never edit
`inventory.py`'s walk itself. A new recommendation rule is a new file with
an `evaluate()` function and a `PRIORITY` constant, plus one line in
`recommendation/rules/__init__.py::RULES`, with its precedence reasoning
added to that file's table. Any future stage added to the Discovery
pipeline (e.g. a Sprint 2 "confirmed" stage) should extend
`PipelineStage` and guard its own entry point with `require_stage()`,
following the same pattern rather than inventing a new one.

---

## The Session domain is a new top-level domain, not folded into Project Intelligence

**Decision**: The ROLE OS Dashboard MVP's Start/End My Day feature lives in
a new `app/session/` domain with its own SQLite file
(`role_os_session.db`), rather than as new fields on `app/projects`
(Project Intelligence) or a new collection type alongside `notes`/
`decisions`/`todos`.

**Why**: A daily session (date, mode, objective, expected result, one
active-at-a-time constraint, a generated Claude prompt, a generated
Markdown record) is a different kind of object from a Project Intelligence
project or its collections — it has its own lifecycle (Not Started →
Active → Completed) and its own uniqueness constraint (at most one active
session system-wide) that doesn't map onto any existing table. Reusing
`app/projects` would have meant either bending its schema to fit an
unrelated concept, or adding session logic to a module whose job is
already fully defined (health scoring, capabilities, dependencies).

**How to apply**: This follows the same test as the Sprint 5 Knowledge
Graph precedent below: a new capability gets its own top-level domain when
it has its own data shape and lifecycle with no logic to share, even if it
superficially touches an existing concept ("projects"). The local project
*registry* the Session page also introduces is deliberately lightweight
(name/status/reference/milestone/next_action) and does not attempt to
replace or sync with Project Intelligence's much richer project model —
they answer different questions ("what ROLE Ecosystem product is this?"
vs. "how healthy is this Project Intelligence project?").

---

## The Session page is a new page, not an extension of Home

**Decision**: The Session page is a new sidebar item/route (`#/session`,
`renderSessionPage()`) rendering entirely separate content from Home.
Home's own markup, data sources, and layout are untouched.

**Why**: Same reasoning as the Sprint 7 Dashboard decision below — Home
already *is* a dashboard, built over Project Intelligence/Advisor/Graph
data. The Session page needs an entirely different question answered
("what am I doing today, and what's my status?") from an entirely
different, brand-new data source (the Session domain), with no natural
shared layout with Home's Today's Focus/Workspace Overview/Health
Dashboard.

**How to apply**: See the Sprint 7 entry below for the general rule this
follows.

---

## Cross-repository reads (ROLE Ecosystem decisions) are opt-in, never path-guessed

**Decision**: `app/session/decisions_adapter.py` only reads
`role-ecosystem/DECISION_LOG.md` live when the user explicitly sets
`ROLE_OS_ECOSYSTEM_DECISION_LOG_PATH`. It never guesses a relative path
between the two repositories, even though on this machine, today, one
exists.

**Why**: `role-ecosystem` and `ROLE_OS` are separate repositories with no
guaranteed common location — a different clone, a different machine, or a
CI runner would break a guessed relative path silently or loudly. Every
other environment-derived value in `app/config.py` already follows this
"explicit env var, honest fallback if unset" pattern; this is the same
seam applied to a cross-repository read for the first time.

**How to apply**: Any future feature that wants to read something from
another ROLE Ecosystem repository should follow this same shape: a
dedicated adapter function, an explicit, documented environment variable
with no default guess, and a clearly-labeled fallback (not a crash, not a
silent empty result) when it isn't configured or the read fails. See
[[../architecture/06_DEVELOPMENT_RULES]]'s "Never duplicate data into a
new store" rule — the fallback here is a deliberately small snapshot, not
a second copy of the full log.

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

---

## Sprint 7's Dashboard is a new page, not an extension of Home

**Decision**: The Dashboard is a new sidebar item/route (`#/dashboard`,
`renderDashboardPage()`) rendering entirely separate content from Home.
Home's own markup, data sources, and layout (Today's Focus, Workspace
Overview, Health Dashboard, Recent Activity, Knowledge Graph Preview,
Quick Search) are untouched.

**Why**: Home already *is* a dashboard — Epic 4 built it as one — but
over a specific pipeline (Project Intelligence, the Advisor's
recommendations, the Epic 3 Graph). Sprint 7 asked for summary
cards/recent activity/system status/quick actions over a different
pipeline entirely (Importer, Explorer, Extraction, the Sprint 5 Knowledge
Graph, Advisor Search) — different endpoints, different metrics, no
overlap. Cramming a second, unrelated set of cards and activity feeds
into Home's existing two-column layout would have meant reworking a page
that already works, for no benefit: nothing about the two pipelines'
data relates closely enough to justify sharing one page's layout logic.

**How to apply**: A new "give me an overview of X" request is a case for
extending an existing overview page only when X is close enough to what
that page already summarizes that a shared layout still reads as one
coherent view. When X is a different pipeline with its own metrics and
no natural connection to the existing page's content, a new page (reusing
the same design-system pieces — card grids, animated counters, activity
lists — without reusing the *page*) keeps both simple.

## Where to go next

- [[../architecture/01_VISION]] and [[../architecture/02_PRINCIPLES]] — the
  standing principles these decisions are instances of.
- [[CHANGELOG_PRODUCT]] — the product-facing history these decisions shaped.
