# 02 — Principles

These are the recurring design principles that show up across every domain
in ROLE OS (Builder, Project Intelligence, Advisor, Knowledge Graph,
Command Center). They aren't aspirational — each one is enforced by the
existing code and test suite, and new work is expected to follow them.

## 1. Deterministic, rule-based, no external AI/LLM API

Every extractor in the Builder, every Health Score signal, every Advisor
rule, and every Knowledge Graph relationship is a pure, deterministic
function over real data — dates, counts, statuses, text overlap. No
randomness, no network calls, no external AI API anywhere in the system.
This makes every output reproducible and fully explainable: a
recommendation or a relationship can always be traced back to the specific
data that produced it.

Where a future AI provider *could* plug in, the seam is explicit and
narrow (e.g. `AdvisorNarrativeProvider` in `app/advisor/narrative.py`) —
it only ever affects *how something reads*, never *what* is computed or
*why*. See [[06_DEVELOPMENT_RULES]].

## 2. Read/compute layers, not new databases

The Advisor and the Knowledge Graph both read from existing databases
(the Builder's knowledge DB, the Project Intelligence DB) and compute
their output fresh on every request, rather than maintaining a duplicate
copy of that data. The Knowledge Graph in particular is explicitly *"a
read/compute layer, not a fourth database."* This means there is never a
sync problem between a project's real state and its representation in the
graph or in a recommendation — there is only one source of truth per kind
of data.

## 3. Additive namespacing, never breaking the layer below

Every new domain gets its own URL namespace (`/pi`, `/advisor`, `/graph`)
specifically so it cannot collide with or require changes to what came
before. Each Epic's changelog entry explicitly confirms that every prior
endpoint and UI surface is unchanged. When two concepts could be confused
(e.g. `/projects`, a knowledge-card classifier, vs. `/pi/projects`,
first-class Project records) they get different names and different
routes rather than overloading one.

## 4. Graceful degradation over missing data

Both the Health Score engine and the Advisor's scoring toolkit combine
multiple independent signals with `weighted_combine`-style renormalization
over whichever signals are actually present, instead of treating a missing
signal as zero. A project with no git integration wired up (the `commits`
signal) is scored fairly on the signals it does have, rather than
penalized for a signal the system doesn't yet collect.

## 5. Independent, single-responsibility units

The Builder's extractors, the Health Score signals, and the Advisor's
rules are each one file with one job: a pure function that takes the
relevant data and returns its piece of the answer. Adding a new signal or
rule means writing one new function and registering it — nothing else in
the system changes. The Knowledge Graph applies the same pattern one level
up: one `build(...) -> (nodes, edges)` function per relationship family
under `app/graph/builders/`.

## 6. Explainability is a first-class output, not an afterthought

Every Advisor recommendation carries `reason`, `evidence`, `suggested_action`,
and `impact` fields built directly from the same data the rule inspected —
never a generic label templated after the fact. Every Knowledge Graph
relationship traces back to a specific row in a specific database. If the
system tells you something, it can also tell you why.

## 7. Plain, dependency-light implementation

The Builder has no third-party dependencies. The Command Center UI is
plain HTML/CSS/vanilla JavaScript with no frontend framework and no build
step. The Knowledge Graph's `models.py` and `queries.py` are dependency-free
pure Python. This keeps the system easy to run, easy to reason about, and
easy to test — a strategic choice, not a temporary one, and not something
to "upgrade" by default.

## 8. UI is presentation only

The Command Center (Epic 4) introduced zero new API surface, database, or
backend logic — it is a pure presentation layer over the API built by
Milestones 1–3 and Epics 1–3. When adding a UI feature, the default
assumption should be that the data it needs already exists behind an
existing endpoint; a new endpoint is the exception, not the rule.

## Where to go next

- [[01_VISION]] — why these principles exist.
- [[03_ARCHITECTURE]] — how they're expressed in the actual system layout.
- [[06_DEVELOPMENT_RULES]] — how to keep following them when adding code.
