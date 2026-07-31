# 09 — Discovery Engine, Sprint 1: Completion Report

Scope executed: read-only filesystem discovery and reporting only, per
`docs/architecture/08_IMPORT_ENGINE_PROPOSAL.md` §18 Phase 1. No project
import, no writes to any production database, no changes to Advisor,
Graph, Assets UI, Mission Control, or Health scoring.

## 1. Files created

```
dashboard/app/discovery/__init__.py       # module docstring / scope boundary
dashboard/app/discovery/models.py         # GitInfo, DiscoveredProject, ScanResult dataclasses
dashboard/app/discovery/detectors.py      # single-pass, read-only folder walker + signal extraction
dashboard/app/discovery/scanner.py        # root-level candidate discovery (depth 1 + nested)
dashboard/app/discovery/git_reader.py     # read-only `git` subprocess calls
dashboard/app/discovery/classifier.py     # confidence / kind / move-risk / maturity / commercial scoring
dashboard/app/discovery/service.py        # orchestration: scan -> detect -> classify -> ScanResult
dashboard/app/discovery/reporters.py      # JSON / Markdown / console table rendering
dashboard/app/discovery/__main__.py       # CLI: `python -m app.discovery audit ...`
dashboard/app/discovery/health.py         # 8-signal Health Score (see §7b addendum)
dashboard/app/discovery/recommendation.py # 6-action Recommendation engine (see §7b addendum)
dashboard/tests/test_discovery.py         # 26 tests (all required scenarios)
dashboard/tests/test_discovery_health_and_recommendation.py  # 12 tests (see §7b addendum)
```

No existing file was modified. `projects/`, `advisor/`, `graph/`, `imports/`,
and every router are untouched.

## 2. Architecture used

Followed §5-§11 of the approved proposal directly:
- `scanner.py` implements §6 (Discovery Pipeline): depth-1 folders are
  always returned; a depth-1 folder without its own strong markers
  (`.git`, `package.json`, `pyproject.toml`, etc.) is treated as a
  container/monorepo and its children are scanned one level deeper,
  admitted only if they show a minimal project signal.
- `detectors.py` implements §7/§9/§10 (Metadata + Asset + partial Repository
  discovery): one bounded walk per candidate folder, symlinks/junctions
  never followed (recorded in `reparse_points_skipped` instead), a
  20,000-file cap with a `truncated` flag, and a byte-budgeted scan for
  hardcoded absolute-path references.
- `git_reader.py` implements the rest of §10: branch, remote, last commit,
  commit count, dirty state — all via local, read-only `git` subcommands
  (no fetch/pull/push).
- `classifier.py` implements §8/§11: transparent weighted heuristics for
  confidence, kind, move risk, maturity, and commercial readiness, each
  carrying a `reasons` list rather than a black-box score.
- `reporters.py`/`__main__.py` implement §7: JSON, Markdown, and a
  console table, behind `python -m app.discovery audit --root ... --output ...`,
  matching the existing `uvicorn app.main:app` / `pythonpath=["dashboard"]`
  convention already used by this repo (confirmed against `pyproject.toml`
  and `dashboard/app/main.py` before choosing this layout).

**Read-only enforcement, concretely:**
- The CLI refuses to run if `--output` resolves to a path inside `--root`.
- The walker only ever calls `os.scandir`/`Path.stat`/`open(..., "r")`.
- `git_reader.py` only issues `rev-parse`, `remote get-url`, `log`,
  `rev-list --count`, and `status --porcelain` — no state-changing command.
- Verified by test (`test_audit_does_not_modify_scanned_tree`,
  `test_reports_written_outside_root_only`): byte-for-byte snapshot of the
  scanned tree before/after a run is identical (excluding git's own
  internal index stat-cache touch, which is git's documented behavior on
  any `git status` call from any tool, not a write this code performs).

## 3. Tests and results

`dashboard/tests/test_discovery.py` — **26/26 passed.** Full existing suite
(`pytest -q` from repo root) — **639/639 passed**, zero regressions.

Coverage against the required list:
| Requirement | Test(s) |
|---|---|
| Nested projects | `test_nested_project_discovered_under_container_folder`, `test_folder_with_own_markers_is_not_descended_into` |
| Git repositories | `test_git_repo_detected_with_branch_and_commit` (branch, hash, message, commit count, dirty-state transition) |
| Non-git folders | `test_non_git_folder_reports_is_repo_false` |
| Paths with spaces/parentheses | `test_path_with_spaces_and_parentheses` (mirrors the real `My Drive (rolevc@gmail.com)` structure) |
| Absolute-path detection | `test_absolute_path_detection_windows_style`, `test_absolute_path_detection_posix_style`, `test_no_absolute_paths_gives_zero_count` |
| Asset counting | `test_asset_counting_images_videos_logos`, `test_docker_and_ci_detection` |
| Classification | 6 tests, one per kind (Software/Documentation/Brand-Asset/Non-project ×2/Mixed) |
| Move-risk scoring | `test_move_risk_high_with_many_absolute_paths`, `_low_with_no_absolute_paths`, `_medium_with_env_file` |
| No filesystem modifications | `test_audit_does_not_modify_scanned_tree`, `test_reports_written_outside_root_only` |
| Invalid roots | `test_invalid_root_raises`, `test_root_is_a_file_raises` |
| Inaccessible folders | `test_inaccessible_folder_is_recorded_not_fatal` (monkeypatched `PermissionError`, scan still completes) |
| Symlink/junction safety | `test_junction_cycle_does_not_hang_or_crash` (junction pointing back at its own parent — a cycle — does not hang or get descended into), `test_analyze_folder_records_reparse_points_skipped` |

Two real bugs were caught and fixed by these tests before this report was
written: (1) the absolute-path regex originally stopped at whitespace,
which broke on real paths containing spaces like `My Drive (email)`; (2)
`.sh` files weren't in the text-scan extension list, so shell scripts with
hardcoded POSIX paths were invisible to the scanner. Both are fixed in
`detectors.py`.

## 4. Discovered projects

**Run 1 — `C:\Users\rolev\Documents`** (not merged with Run 2, per instruction):
29 folders discovered, 0 errors, 3 reparse points skipped, ~5.6s.
Full reports: `var/discovery_reports/documents/documents_audit.{json,md}`.

| Classification | Count |
|---|---|
| Software Project | 2 (`AGUA-AZUL-APP` container + `agua-azul-app` nested repo) |
| Mixed Project | 5 (`charcos-site`, `desierto-creativo-site`, `role-content-factory`, `rolevaldez.com`, `SUPER-FACIL`) |
| Non-project | 22 (app-data folders: ACID Pro, Audacity, PowerToys, OneNote Notebooks, etc.) |

`role-content-factory` scored confidence 1.00, maturity "mature", and
commercial-readiness "client-ready" — the strongest real signal in this
root.

**Run 2 — `C:\Users\rolev\My Drive (rolevc@gmail.com)\1 - IA PROJECTS`**
(the real project root): 17 folders discovered, 0 errors, 0 skipped, ~7.8s.
Full reports written to the session scratchpad (see note in §7 — could not
be written under `var/` without violating the read-only-outside-root rule,
since ROLE_OS itself lives inside this root).

| Classification | Count |
|---|---|
| Software Project | 2 (`ROLE_KNOWLEDGE_OS`, `ROLE_OS_BUILDER`) |
| Website | 2 (`RCOM-Printful-Adapter`, `RCOM-Shopify-Adapter`) |
| Mixed Project | 4 (`OTROS - no proyectos`, `ROLE Commerce Factory`, `role-ecosystem`, `ROLE_OS`) |
| Documentation Project | 1 (`ROLE MASTER`) |
| Unknown | 8 (nested folders under `ROLE Commerce Factory`: `01_BRAND_CORE`, `02_PROMPT_SYSTEM`, `03_PROJECTS`, `04_ASSETS`, `05_DOCUMENTATION`, `07_PROMPT_ENGINE`, `08_REFERENCE_LIBRARY`, `09_ASSET_LIBRARY`) |

`ROLE_OS` itself scored confidence 1.00, maturity "mature",
commercial-readiness "client-ready" — the classifier correctly recognized
the most active real project on the machine without being told anything
about it.

## 5. Likely duplicates

- **`AGUA-AZUL-APP` / `agua-azul-app`** (Documents root): a depth-1 folder
  `AGUA-AZUL-APP` containing a nested depth-2 folder `agua-azul-app` that is
  itself the real git-backed project. This is very likely one project
  represented twice (a wrapper folder around its own repo), not two
  distinct projects. Needs a human decision, not an automatic merge.
- No cross-root duplicates were checked, per instruction #13 (the two
  audits were kept separate and not merged/deduplicated against each
  other).

## 6. Move-risk findings

**High risk** (>5 hardcoded absolute-path references found in scanned text):
| Project | Root | Refs |
|---|---|---|
| `ROLE_OS` | `1 - IA PROJECTS\ROLE_OS` | 130 |
| `ROLE_KNOWLEDGE_OS` | `1 - IA PROJECTS\ROLE_KNOWLEDGE_OS` | 27 |
| `ROLE_OS_BUILDER` | `1 - IA PROJECTS\ROLE Commerce Factory\ROLE_OS_BUILDER` | 27 |
| `SUPER-FACIL` | `Documents\SUPER-FACIL` | 6 |

These are overwhelmingly expected: this is ROLE OS's own codebase and docs,
which legitimately reference `C:\Users\rolev\...` paths as configuration
examples and default settings (e.g. `dashboard/app/config.py`'s documented
defaults). This is not a defect — it is exactly the signal the proposal's
§17 risk table asked this feature to surface, so that a future "move this
folder" or "share this repo" action knows what would break.

**Folders safe to move** (move_risk = low): the two site projects in
Documents (`charcos-site` low, `desierto-creativo-site` low) and
`role-ecosystem`/`RCOM-*` adapters (low/medium) in the real project root.
Full list is in the JSON/Markdown reports; not reproduced here in full to
keep this report short.

## 7. Limitations (read before trusting any single score)

- **`OTROS - no proyectos` was scanned and classified as "Mixed Project."**
  The user explicitly stated this folder holds everything that is *not* a
  real project. Sprint 1 has no exclusion-list mechanism — it scans
  everything under the given root indiscriminately. This is the single
  biggest known false-positive risk in Run 2's results and should be the
  first thing fixed in Sprint 2 (a configurable ignore-list, not a
  hardcoded name check).
- The classifier is a transparent weighted heuristic, not ML — it can be
  wrong on unusual folder layouts. Every score carries its `reasons` list
  precisely so a human can catch this.
- Commercial-readiness is a very weak signal (keyword matches inside
  already-scanned text plus CI/Docker/tests presence). Treat it as a
  conversation starter, not a fact.
- The 8 "Unknown" nested folders under `ROLE Commerce Factory` are numbered
  content folders (`01_BRAND_CORE`, etc.) with weak, ambiguous signal —
  correctly not force-classified into a wrong bucket, but also not useful
  yet. This is a asset/brand-project detection gap the next sprint should
  address (§9 of the proposal covers deeper asset classification).
  Note: I could not confirm/verify this in the repo yet — the assets
  detection logic here is the same as everywhere else; the ambiguity is
  intrinsic to those folders' contents (mostly numbered subfolders one
  level too deep for this sprint's `max_depth=2`).
- Report for Run 2 could not be written under `ROLE_OS/var/` — that
  directory is inside the scanned root, and the CLI's read-only guard
  correctly refused. Reports for that run currently live only in this
  session's temp scratchpad; if you want them preserved, they should be
  copied to a location outside `1 - IA PROJECTS` (e.g. a separate reports
  drive/folder), which is itself a Sprint 2 concern (§13 "Mission Control
  Integration" needs a permanent, non-scanned place for audit history).
- `git rev-list --count HEAD` can be slow on very large histories; not an
  issue at the project counts seen here (single digits to low tens), but
  worth knowing if this is ever pointed at a folder with a huge monorepo.
- Windows junction test (`test_junction_cycle_does_not_hang_or_crash`)
  passed on this machine but is skipped automatically on platforms/setups
  where junction creation fails — it is not a guaranteed CI signal
  everywhere, only here.

## 7b. Addendum — Health Score, Recommendation engine, and three more detectors

Added on top of the above without changing any existing scanner/detector/
classifier behavior (all 26 original tests still pass unmodified):

- **`health.py`** — an 8-signal, 0-100 Health Score (documentation, tests,
  recent activity, roadmap, architecture, automation, commercial
  readiness, deployment), weighted and renormalized over whichever signals
  are available, mirroring `dashboard/app/projects/health/`'s existing
  Health Score engine shape but scored from filesystem evidence.
- **`recommendation.py`** — one of the six actions requested for the
  Discovery Audit deliverable (`Leave where it is` / `Move into IA
  PROJECTS` / `Archive` / `Merge with another project` / `Rename` /
  `Requires manual review`), each with the specific reasons behind it.
  `apply_container_child_overrides` is a corpus-level pass that flags a
  container folder whose only nested project shares its name (the
  `AGUA-AZUL-APP` / `agua-azul-app` case from §4/§5 below) as `Rename`,
  without touching the nested project's own recommendation.
- New detectors: `has_license` (LICENSE/LICENSE.md/etc.), `has_obsidian_vault`
  (`.obsidian/`) and `vscode_workspace_files` (`*.code-workspace`) — both
  now factor into move-risk scoring alongside the existing absolute-path/
  `.env`/launcher-script signals — plus `document_count`/`design_file_count`/
  `font_count` (`.pdf`; `.psd`/`.ai`/`.xd`/`.fig`/`.sketch`; `.ttf`/`.otf`/
  `.woff`/`.woff2`).
- `reporters.py`'s Markdown Summary section now reports the exact
  breakdown the Discovery Audit spec asked for (folders scanned, projects
  detected, git repositories, static websites, Python/Node projects,
  unknown folders, safe-to-move/needs-review/high-risk counts); the
  Projects table is `| Project | Type | Git | Health | Move Risk |
  Recommendation |`; a new Recommendations section lists every folder's
  action and reasoning.
- 12 new tests in `dashboard/tests/test_discovery_health_and_recommendation.py`.
  Full suite: **651/651 passed**, zero regressions.

**Re-run against the real project root** (`1 - IA PROJECTS`, same 17
folders as Run 2 in §4) with the enhanced engine:

| Project | Type | Git | Health | Move Risk | Recommendation |
|---|---|---|---|---|---|
| OTROS - no proyectos | Mixed Project | - | 46 | medium | Requires manual review |
| ROLE Commerce Factory | Mixed Project | - | 86 | medium | Move into IA PROJECTS |
| ROLE MASTER | Documentation Project | - | 48 | medium | Requires manual review |
| role-ecosystem | Mixed Project | main@3ca8c89 | 55 | low | Move into IA PROJECTS |
| ROLE_KNOWLEDGE_OS | Software Project | - | 48 | high | Requires manual review |
| ROLE_OS | Mixed Project | main@470d56c | 79 | high | Requires manual review |
| 01_BRAND_CORE … 09_ASSET_LIBRARY (8 folders) | Unknown | - | 37 | low | Requires manual review |
| RCOM-Printful-Adapter | Website | - | 56 | medium | Move into IA PROJECTS |
| RCOM-Shopify-Adapter | Website | - | 56 | medium | Move into IA PROJECTS |
| ROLE_OS_BUILDER | Software Project | - | 44 | high | Requires manual review |

Summary: 17 folders scanned, 17 "projects" detected (none classified
Non-project in this root — expected, since everything under `1 - IA
PROJECTS` is deliberately project-shaped), 2 git repos, 2 static websites,
3 Python projects, 5 Node projects, 8 unknown, 9 safe to move, 13 needing
review, 3 high risk (`ROLE_KNOWLEDGE_OS`, `ROLE_OS`, `ROLE_OS_BUILDER` —
the same three flagged in §6, unchanged by this addendum).

**Known limitation surfaced by this re-run**: `recommendation.py` always
labels its "safe to consolidate" action `Move into IA PROJECTS` regardless
of what root was actually scanned — so when the scanned root *is* `1 - IA
PROJECTS` itself (as here), folders like `ROLE Commerce Factory` and
`role-ecosystem` get told to move into the folder they already live in.
The recommendation engine has no notion of "the scan root already is the
destination"; this is cosmetic (the *reasoning* — health score, move risk —
is still correct) but should be fixed before Sprint 2 wires this into a
UI, e.g. by naming the action relative to the scanned root instead of a
hardcoded destination string.

## 7c. Sprint 1.5 — Structural Hardening (registry/rule-engine architecture)

Pure refactor, no new product behavior, per the Sprint 1.5 brief (see
`docs/product/DECISIONS.md`'s "Discovery Engine Sprint 1.5" entry for the
full why/how):

- `detectors.py` (one ~150-line function) → `detectors/` package: a shared
  `inventory.py` walk (raw facts, zero interpretation) + twelve independent
  detector modules, each a `Findings` dataclass and a pure `detect()`
  function, merged by `registry.run_all()` with a field-collision guard.
- `recommendation.py` (if/elif ladder) → `recommendation/` package: six
  independent rules (`rules/*.py`), each with an explicit `PRIORITY`;
  `engine.recommend()` runs all of them and keeps the highest-priority
  match. Precedence is a documented table in `rules/__init__.py`, not
  implicit code-flow ordering — verified rule-order-independent by test.
- New `pipeline.py`: a `PipelineStage` enum stamped onto
  `DiscoveredProject.stage`, guarding `health.compute_health()` (requires
  `CLASSIFIED`) and `recommendation.recommend()` (requires `SCORED`) so
  calling either out of sequence raises `PipelineStageError` instead of
  silently scoring incomplete data.
- `analyze_folder()`, `classify()`, `compute_health()`, `recommend()`, and
  `apply_container_child_overrides()` all kept their exact Sprint 1
  signatures — `scanner.py`, `service.py`, and every existing test needed
  zero changes to their import statements.

**Parity, proven not assumed**: re-ran the CLI against both real corpora
from §4 (`Documents`, `1 - IA PROJECTS`) after the refactor. Markdown
output was byte-for-byte identical to the pre-refactor reports, except one
line — `ROLE_OS`'s own git commit hash, which changed because of an
unrelated commit made between runs, not a behavior change. 25 new tests
added (`test_discovery_sprint1_5_structure.py`,
`test_discovery_sprint1_5_parity.py`, plus 2 more in
`test_discovery_health_and_recommendation.py` for the new pipeline guard);
zero existing Discovery tests were modified. Full repo suite: 718 passed,
0 failed.

Two pre-existing Sprint 1 quirks were deliberately preserved rather than
quietly fixed, since either would have changed observable output:
`go.mod` files are double-counted in `tech_markers` (documented in
`detectors/markers.py`), and `DiscoveredProject.frameworks` remains always
empty (no detector ever populated it, in Sprint 1 or here).

## 8. Recommended Sprint 2

Per the proposal's own rollout plan (§18 Phase 2/3, §19 Sprint 2), and
informed by what Run 1/Run 2 actually surfaced:

1. **Exclusion-list support** in `scanner.py` (config-driven, not
   hardcoded) — directly motivated by the `OTROS - no proyectos`
   false-positive above.
2. **`discovered_assets` / `discovered_repos` tables** (§14 of the
   proposal) — Sprint 1 deliberately kept everything in-memory
   (`DiscoveredProject` dataclasses); Sprint 2 is where this becomes
   durable and queryable.
3. **`classifier.py` confidence-threshold review using Run 2's real
   output** before wiring a confirm/reject UI — the 8 "Unknown" nested
   folders are a good concrete test case for tuning the threshold.
4. **`/discovery/scan` and `/discovery/candidates` API + confirm/reject
   flow** (§15/§16.3) — still writes nothing to `projects` automatically;
   first write only happens on human confirmation, per the approved
   migration strategy.
5. Do **not** yet touch Advisor/Graph/Health/Mission Control — that stays
   Sprint 3/4 per the approved plan, once the classifier has been
   validated against a second real run's output.
