# 15 — Project Context, Sprint C1B (Rewiring): Completion Report

Scope executed: an independent audit of Sprint C1 (see the audit artifact
referenced in `docs/product/DECISIONS.md`) found `ProjectContext` had
exactly one production caller -- Cockpit's optional `/project-context/{id}`
fetch, wrapped in a swallowed try/catch, for one field. Every other
project-oriented screen (Home, Projects, Workspace, Advisor) still
independently assembled its own project data, and the module's own
health-tier thresholds (80/50) disagreed with the frontend's (70/40) -- a
project scoring 75 was "healthy" via the API and "warning" everywhere it
was actually rendered. Sprint C1B's job: make `ProjectContext` load-
bearing, without redesigning it or the systems it composes. No version
bump, no commit, no tag.

## 1. Architecture: before / after

**Before** -- the builder sat beside the real data paths, downstream of
the modules it claimed to unify, consumed by nothing but its own router
and one non-critical UI fallback:

```
Cockpit --(1 field, try/catch)--> /project-context/{id} --> builder
Home, Projects, Workspace, Advisor --> their own pre-existing assembly (unchanged)
```

**After** -- every listed production endpoint embeds a real
`project_context` per project, built from data the router already fetched
(no duplicate enrichment pass):

```
/workspace/home                        ─┐
/workspace/discovered?view=top_level    │
/workspace/discovered/{id}              ├──> project_context.builder ──> ProjectContext dict
/pi/projects, /pi/projects/{id}         │      (health.health_tier, discovery.next_action,
/workspace/advisor                      │       workspace.resume.preview_resume_state,
/advisor/recommendations               ─┘       workspace.assets_index)
```

## 2. Exact production callers (verified)

| Endpoint | Screen | Embedding |
|---|---|---|
| `GET /workspace/discovered?view=top_level` | Projects, Workspace | `project_context` per item |
| `GET /workspace/discovered/{item_id}` | Project Detail | full-cost `project_context` |
| `GET /workspace/home` | Home | `project_context` on every project reference |
| `GET /workspace/advisor` | Advisor (Workspace) | `project_context` per recommendation |
| `GET /advisor/recommendations` | Advisor (Epic 2) | `project_context` per recommendation |
| `GET /pi/projects`, `GET /pi/projects/{id}` | Cockpit, manual Projects | `project_context` per project |

Cockpit's frontend no longer makes a separate `/project-context/{id}`
fetch -- it reads `project.project_context` off the `/pi/projects` row it
fetched anyway (verified by a test asserting the old fetch is gone).

## 3. Duplicate logic removed

- **Inline next-action mini-extractor** (hardcoded 0.6 confidence) --
  deleted. A manual project's AI-session hint now routes through the same
  `discovery.next_action.extract_next_action` a discovered item uses (its
  `ai_session` branch short-circuits before touching the filesystem, so
  it's safe with no `root_path`). Same source, same confidence (0.95),
  everywhere.
- **Disconnected `resume_state` stub** -- deleted. `workspace/resume.py`
  gained `preview_resume_state()`, a read-only mirror of the real
  `resume_work()` orchestration (same lookups, no mutation).
- **Cheap asset-count divergence** -- `ProjectContext.assets_count` now
  calls `assets_index.index_assets_for_project` directly, the same
  function `/workspace/assets` uses.
- **Health-tier threshold contradiction** -- `app/project_context/
  health.py` is the one place `HEALTHY_THRESHOLD=80`/`WARNING_
  THRESHOLD=50` exist; the frontend's fallback is hand-synced and pinned
  by a test parsing the JS source.
- **Four JS status-badge functions** now render through one shared
  `badgeHtml()` helper -- their distinct status vocabularies (AI session,
  PI project, Daily Session, Workspace adoption state) were correctly left
  unmerged.

## 4. Canonical decisions

- **Health**: 80/50 thresholds; `health_score_source` (`"discovery"` |
  `"project_intelligence"` | `None`) names which of the two distinct
  scoring algorithms produced a score, rather than merging them.
- **Next action**: `discovery.next_action.extract_next_action` is the only
  extractor, for both discovered and manual projects.
- **Resume**: `resume_work()` (mutating) and `preview_resume_state()`
  (read-only) are the only two resume code paths.
- **Assets**: `assets_index.index_assets_for_project` is the single source
  of truth.
- **Timeline vs. Recent Activity**: kept as two intentionally distinct
  datasets (AI-Sessions/Snapshots vs. the broader git/filesystem/adoption/
  session/asset feed).

## 5. Tests and results

- `dashboard/tests/test_project_context_rewiring.py` (new, 13 tests):
  screen-acceptance embedding checks, asset-count parity, resume-state
  parity before/after a real resume call, health-tier threshold parity
  between the Python constant and the JS source, timeline-vs-recent-
  activity distinctness, manual + discovered end-to-end regression.
- `test_project_context_builder.py`/`_api.py`/`_ui.py` updated for
  corrected (not just changed) behavior.
- Full suite: 909 passed. ruff (`--select E9,F`) clean. black clean. JS
  syntax valid.

## 6. Live verification

Ran the real dashboard against the real ROLE OS workspace (17 discovered
projects, 5 adopted): `/pi/projects` and `/workspace/discovered?view=
top_level` both returned real projects with `project_context` embedded
(e.g. ROLE Commerce Factory, health_score=86, tier "healthy" under 80/50).
Browser check on Home, Cockpit, Workspace, Advisor: zero application
console errors; Cockpit showed the correct health badge and an enabled
Resume Work button for a real project.

## 7. Remaining exceptions (explicit)

1. `services/launcher.py`'s `_pending_tasks_block` reads Daily Session's
   own manually-typed registry fields -- a different domain, out of scope
   per "do not add features."
2. Workspace's nested hierarchy (children/repositories/components) does
   not carry its own embedded `project_context` per child row.
3. Dashboard, Explorer, Knowledge confirmed as genuinely non-project
   domains -- no change needed.
4. `portfolio.py`'s ranking/scoring algorithms were left as-is --
   `ProjectContext` supplies the canonical description once a project is
   selected; selecting it is a recommendation algorithm, not project-data
   assembly.

## 8. Updated architecture score: 8/10

Up from the audit's 3/10. Not a 10 because the frontend's `healthTier`
fallback is synced, not eliminated; there is no CI guard yet against a
*new* project-oriented route bypassing `ProjectContext`; and Workspace's
child/repository rows still don't get the canonical projection.
