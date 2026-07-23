# 06 — Development Rules

Concrete rules for contributing to ROLE OS, derived from what every past
Epic/Milestone has actually done (see [[07_ROADMAP]] and `CHANGELOG.md`
for the precedent behind each rule).

## Hard constraints

1. **Never call an external AI/LLM API.** No extractor, health signal,
   Advisor rule, or Graph relationship may depend on a model call or
   network access. This is enforced by every Epic's own changelog entry
   ("This Epic does not call OpenAI, Claude, or any external API") and is
   core to [[01_VISION]] and [[02_PRINCIPLES]] §1.
2. **Never duplicate data into a new store.** If you need to derive
   something from existing data, compute it on read (like the Advisor and
   the Knowledge Graph do) rather than persisting a redundant copy that can
   drift out of sync.
3. **Never modify an existing, shipped endpoint's contract.** Add new,
   additively namespaced endpoints instead (`/pi`, `/advisor`, `/graph`
   are the precedent). If two concepts could be confused, give them
   different names/routes rather than overloading one — see the
   `/projects` vs. `/pi/projects` split.
4. **UI changes do not get new backend surface** unless the data genuinely
   doesn't exist yet behind an API. Epic 4 (the entire Command Center
   redesign) introduced zero new endpoints, database, or backend logic.

## Where new code goes

- A new **Builder extraction concern** → `builder/extractors/<name>.py`,
  one pure function, wired into `build_knowledge_card()` in
  `extractors/__init__.py`.
- A new **Health Score signal** → `dashboard/app/projects/health/<name>.py`,
  a pure function, registered with a weight in
  `health/__init__.py::compute_health_score()`.
- A new **Advisor rule** → `dashboard/app/advisor/rules/<name>.py`, a pure
  `evaluate(project, context) -> list[RecommendationCandidate]` function,
  registered in `app/advisor/engine.py`. Reuse `app/advisor/scoring.py`
  for priority/staleness/confidence/effort calculations rather than
  reimplementing scoring math per rule.
- A new **Knowledge Graph relationship family** →
  `dashboard/app/graph/builders/<name>.py`, a pure
  `build(...) -> (nodes, edges)` function, merged in
  `app/graph/engine.py::build_graph()`. New node or relationship types must
  be added to the fixed vocabularies in `app/graph/models.py` and reflected
  in `GET /graph/meta/types`.
- A new **UI page/interaction** → see [[05_UI_GUIDELINES]].

## Testing

Run the full suite from the repo root:

```bash
pip install -r dashboard/requirements.txt pytest
python -m pytest
```

`pyproject.toml` configures `testpaths = ["tests", "dashboard/tests",
"builder/tests"]` with `pythonpath = ["dashboard", "builder"]`, so pytest
run from the repo root discovers all three suites without extra flags.

Expectations, by precedent:

- **Every new pure function gets a unit test.** Every extractor, health
  signal, and Advisor rule in the codebase has one.
- **Every new endpoint gets an API test** using FastAPI's `TestClient`
  (see `dashboard/tests/test_*_api.py`).
- **Every Epic includes a regression check** that all prior API/UI surface
  is unaffected — don't skip this when adding a domain; it's what lets
  Epics stack without fear of breaking earlier ones.
- **Integration tests exercise real data flow**, not mocks-all-the-way-down
  — e.g. `build_graph()` is tested against real Project Intelligence and
  knowledge databases, including graceful degradation when one is missing.

Formatting/linting config exists for `black` and `ruff` at line-length 100,
Python 3.10 target (`pyproject.toml`).

## Backward compatibility

When changing an existing module's internals, keep old call sites working
if anything outside the module might still use them — `knowledge_extractor.py`
is kept as a thin backward-compatible wrapper (`build_card`) around
`extractors.build_knowledge_card` for exactly this reason. Prefer this
pattern over a breaking rename, unless the user has explicitly asked for a
breaking change.

## Documentation

When a change is user-visible or changes the API surface, update:

- `CHANGELOG.md` — one entry per Epic/Milestone, following the existing
  style (what was added, what new files/modules appeared, what stayed
  unchanged, test counts).
- `README.md` and `dashboard/README.md` — keep the endpoint tables and
  "Status" sections current.
- This `docs/architecture/` set, if the change affects vision, principles,
  architecture, data model, UI, or roadmap — and `docs/product/DECISIONS.md`
  / `CHANGELOG_PRODUCT.md` if it reflects a product-level decision or
  externally visible change (see [[../product/DECISIONS]]).

## Where to go next

- [[02_PRINCIPLES]] — the reasoning behind these rules.
- [[07_ROADMAP]] — what's shipped, so you know what precedent to follow.
