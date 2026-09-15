# Role OS 2.0 — Phase 2 Multi-Root Discovery

## Problem

Role's real, active projects exist outside Role OS's single default Discovery scan root. `CURRENT_STATE.md`/`NEXT_ACTIONS.md` already named six real projects — `role-content-factory`, `rolevaldez.com`, `SUPER-FACIL`, `AGUA-AZUL-APP`, `charcos-site`, `desierto-creativo-site` — all confirmed to live under `C:\Users\rolev\Documents`, structurally invisible to Role OS because the Discovery Engine only ever scanned one configured root. This is a direct gap in the "PROJECT" step of the core chain: Mission Control cannot recommend or track work it never sees.

`PROJECT_REGISTRY.md` (created by a separate, concurrent Claude Code session doing a broader Role-Ecosystem backup/inventory pass, unrelated to this task) independently confirmed several of these same locations plus additional ones (`bolsa-de-trabajo`) — used here only as discovery evidence, per this task's brief. It is not treated as a canonical runtime database, an adoption list, or a competing project-state system.

## Previous Single-Root Behavior

- `dashboard/app/config.py: Settings.discovery_root` — one string, from `ROLE_OS_DISCOVERY_ROOT`, defaulting to the repo's parent directory.
- `dashboard/app/workspace/service.py: rescan()` — `target_root = root or settings.discovery_root`; raised `ValueError` if empty; otherwise called `app.discovery.service.run_audit` exactly once and cached the single resulting project list.
- `dashboard/app/workspace/db.py` — one singleton `workspace_scan_cache` row (`id = "singleton"`), `root` stored as one plain string.
- Project identity (`app/discovery/identity.py: compute_item_id`) was already root-agnostic — a SHA1 hash of `root_path` alone — so nothing about identity itself assumed a single root; the assumption lived entirely in *how many times, and with what root(s),* `run_audit` was called.
- The only way to widen the scan was to manually pass a different `root` to the Discovery CLI or the `/workspace/rescan` API call, once, by hand (as Task 9's archived audit report did).

## Multi-Root Model

The smallest change that closes the gap: `rescan()` can now be given *multiple* roots to scan, each through the exact same, unmodified `run_audit` pipeline, with the results merged into one cached project list before Workspace ever sees them.

**New/changed files:**
- `dashboard/app/discovery/roots.py` (new) — `resolve_roots(raw_roots) -> RootsResolution`. Validates and deduplicates a list of configured roots (existence, directory-ness, exact/case-insensitive duplicates, nesting) before any of them is scanned. Pure, read-only, no dependency on `Settings` or the scan pipeline itself.
- `dashboard/app/config.py` — `Settings.get_discovery_roots()` (new method). Reads `ROLE_OS_DISCOVERY_ROOTS` (comma-separated) if set and non-empty; otherwise falls back to `[self.discovery_root]` (still the existing `ROLE_OS_DISCOVERY_ROOT` variable). Computed live on each call, not cached at `__init__`, so it stays consistent with every other environment-driven field in this class.
- `dashboard/app/workspace/service.py: rescan()` — rewritten to branch on how many roots are in play (see below), extracting the original single-root scan-and-cache logic unchanged into `_rescan_single_root()`.

## Configuration

`ROLE_OS_DISCOVERY_ROOTS` — new, optional, comma-separated list of absolute folder paths, e.g.:

```
ROLE_OS_DISCOVERY_ROOTS=C:\Users\rolev\My Drive (rolevc@gmail.com)\1 - IA PROJECTS,C:\Users\rolev\Documents
```

If unset or blank, behavior is unchanged: `ROLE_OS_DISCOVERY_ROOT` (a single value, same as before this task) is used, or none at all if that is also unset. No new persisted concept, no new UI, no explicit-project-registration allow-list (evaluated and rejected in `docs/ROLE_OS_2_PHASE_2_PLAN.md` §6 for adding a second, competing source of truth) — this is pure environment configuration, exactly the mechanism the plan recommended.

An explicit `root` argument (as the `/workspace/rescan` API, and every existing test, already always passes) is untouched: it always scans exactly that one root, exactly as before this task existed. Multi-root logic is only ever consulted when `root` is `None`.

## Root Validation

`resolve_roots()` (`app/discovery/roots.py`) performs, per configured root:

1. Strip whitespace; skip empty entries.
2. `Path(raw).resolve()` — caught `OSError` is recorded as "could not resolve path", not fatal to the rest of the list.
3. `exists()` — missing roots are recorded as "does not exist" and skipped.
4. `is_dir()` — a file is recorded as "not a directory" and skipped.
5. Case/slash-insensitive duplicate detection (`os.path.normcase(os.path.normpath(...))` as the comparison key, so `C:\Foo` and `c:\foo\` collapse to the same root on Windows) — the second and later occurrences are recorded as "duplicate of already-configured root: …" and skipped.
6. Nested-root detection — any surviving root that is a strict subdirectory of another surviving root is recorded as "nested inside already-configured root: …" and dropped (scanning both would let the same project appear under two different `root_path` prefixes... in practice it can't, since `root_path` is always the absolute folder path regardless of which root found it, but avoiding the nested scan avoids doing redundant filesystem work and avoids ever presenting the same folder as both a project and something's "root").

Every skip is a `RootDiagnostic(root, reason)`, never a hard failure — one bad root (typo, drive unplugged, permission issue) does not prevent the others from being scanned. `rescan()` only raises `ValueError` if *zero* roots survive validation.

## Deduplication

Two independent layers, matching the plan's "use existing project identity logic wherever possible" instruction:

1. **Root-level** (`resolve_roots`): exact duplicates and nested roots are removed *before* any scanning happens, so the same folder is never scanned twice from two different configured roots in the first place.
2. **Project-level** (`rescan`'s multi-root branch): as a defense-in-depth safety net, every discovered project's `discovery_id(root_path)` (`app.discovery.identity.compute_item_id` — unchanged, already root-agnostic) is tracked in a `seen_ids` set while merging each root's results; a second occurrence of the same id is dropped rather than appended. No new identity system was introduced — this reuses the exact hash every other Workspace lookup (`list_workspace_items`, `get_item`, adoption, overrides) already depends on.

## Project Identity

Unchanged. `compute_item_id(root_path)` was always a pure function of the absolute folder path, with no notion of "which root found this." A project's Workspace item id is therefore identical whether it was found via a single-root scan or a multi-root scan — verified directly by `test_rescan_multi_root_project_ids_stable_and_match_single_root_scan` (`dashboard/tests/test_workspace_service.py`). Existing adopted-project rows (keyed by `root_path`, per `app/workspace/db.py`) are unaffected by enabling additional roots.

## Discovery vs. Adoption

Multi-root scanning only ever populates `workspace_scan_cache` (the read-only "what does the filesystem currently look like" cache). The `adopted_projects` overlay table — and therefore `projects_adopted`/`projects_ignored` counts, the Projects page, Mission Control, and Resume Work — is untouched by rescanning alone, regardless of how many roots are configured or how many new projects a rescan surfaces. A newly-discoverable project is visible in `list_workspace_items`/`list_hierarchy` with `adopted: false`, exactly like every previously-discoverable-but-unadopted project always has been. Adoption remains the same explicit, one-at-a-time `POST /workspace/{id}/adopt` action it always was — nothing in this task calls it automatically. Verified directly by `test_rescan_multi_root_never_auto_adopts_discovered_projects`.

## Known Project Coverage

Live, read-only validation (temp workspace DB — see "Live Validation" below) with `ROLE_OS_DISCOVERY_ROOTS` set to the repo's existing default root plus `C:\Users\rolev\Documents`:

| Name | Path | Discovery root | Exists | Classification | Already adopted? |
|---|---|---|---|---|---|
| role-content-factory | `C:\Users\rolev\Documents\role-content-factory` | `Documents` | Yes | Mixed Project | NO |
| rolevaldez.com | `C:\Users\rolev\Documents\rolevaldez.com` | `Documents` | Yes | Mixed Project | NO |
| AGUA-AZUL-APP | `C:\Users\rolev\Documents\AGUA-AZUL-APP` | `Documents` | Yes | Software Project | NO |
| agua-azul-app | `C:\Users\rolev\Documents\AGUA-AZUL-APP\agua-azul-app` | `Documents` | Yes | Software Project | NO |
| charcos-site | `C:\Users\rolev\Documents\charcos-site` | `Documents` | Yes | Mixed Project | NO |
| desierto-creativo-site | `C:\Users\rolev\Documents\desierto-creativo-site` | `Documents` | Yes | Mixed Project | NO |

**Not currently discoverable** (path named in `NEXT_ACTIONS.md`/`PROJECT_REGISTRY.md` does not exist on disk today — not a Discovery defect, verified directly with `Test-Path`):
- `SUPER-FACIL` — no matching folder found under `C:\Users\rolev\Documents`; `PROJECT_REGISTRY.md` registers a similarly-named "Role Super Facil" under the *existing* Drive root instead (already discoverable, unrelated path).
- `bolsa-de-trabajo` — `PROJECT_REGISTRY.md`'s listed path, `C:\Users\rolev\Documents\bolsa-de-trabajo`, does not exist; `Test-Path` confirms. Likely moved, renamed, or the registry entry is stale — a discrepancy to flag to Role, not something this task resolves. **Update (2026-09-14, after this task):** the registry's path was wrong, not the project — Role confirmed the real path is `C:\Users\rolev\bolsa-de-trabajo` (one level up), corrected in `PROJECT_REGISTRY.md` (`9bf4af4`) and verified (`.git` present, remote matches, last commit 2026-09-02). It is real and **ACTIVE**, still outside every currently-configured Discovery root — see `docs/PHASE_2_MISSION_CONTROL_DAILY_USE_REVIEW.md`'s "Discovery / Isolated Repository Note" for the current status and the future-mechanism discussion it prompted.

Every one of the ~30 unrelated `Documents` entries (`ACID Pro 7.0 Projects`, `Audacity`, `BarTender`, `Zoom`, etc.) that Task 9's archived audit already flagged as clutter was again correctly classified `Non-project` by the existing, unmodified classifier — multi-root scanning required no new precision mechanism, exactly as the plan predicted (§6).

**Total discovered across both roots in this validation run: 53** (up from whatever a single-root scan of the repo's parent alone would find — the existing default root's own count is unaffected, since that root is still scanned by the exact same unmodified pipeline as before).

**Projects adopted by this validation: 0.** **Existing adopted-project count: unchanged (0 in this temp/isolated validation DB; 5 in the real canonical DB, untouched — see "Runtime Safety").**

## PROJECT_REGISTRY.md Relationship

`PROJECT_REGISTRY.md` was used exactly as instructed: as discovery/configuration *evidence* (it independently confirmed several of the same real project locations, plus surfaced `bolsa-de-trabajo` as one more to check) — never as a source Discovery reads at runtime, never as a competing adoption list, and never as a second project-state database. Role OS's Discovery Engine has no code path that reads `PROJECT_REGISTRY.md`; it remains a human/AI-facing index document, unrelated to the `workspace_scan_cache`/`adopted_projects` tables this task touches.

## Tests

New:
- `dashboard/tests/test_discovery_roots.py` — 10 tests, `resolve_roots()` in isolation: single root, two independent roots, nonexistent root, file-not-a-directory, exact duplicate, case-duplicate (Windows), nested root (both configuration orders), blank/whitespace entries, empty list.
- `dashboard/tests/test_config.py` — 5 new tests: `get_discovery_roots()` falls back to the single `discovery_root` when `ROLE_OS_DISCOVERY_ROOTS` is unset; empty single root yields an empty list; comma-separated parsing; the multi-root env var takes precedence over the single-root fallback; a blank/whitespace-only env var value falls back correctly.
- `dashboard/tests/test_workspace_service.py` — 8 new tests: no-explicit-root-single-configured-root is byte-for-byte unchanged; multi-root merges projects from both roots; the reported `root` names both scanned roots; a duplicate configured root does not duplicate projects; nested configured roots do not duplicate projects; a nonexistent configured root is skipped without failing the whole rescan; project ids are identical whether found via a single-root or multi-root scan; multi-root rescan never auto-adopts anything.

Run:
- `dashboard/tests/test_discovery_roots.py`, `test_config.py`, `test_workspace_service.py`, `test_workspace_db.py`, `test_workspace_api.py` — **82 passed**.
- Regression slice (`test_workspace_hierarchy_api.py`, `test_workspace_sprint4_api.py`, `test_workspace_sprint5_api.py`, `test_mission_control_api.py`, `test_mission_control_freshness_ui.py`, `test_assets_os.py`, `test_project_ecosystem.py`, `test_executive_decision.py`, `test_impact_analysis.py`, `test_session_intent.py`) — **220 passed**.
- Root-level `tests/` + `builder/tests/` — **34 passed**.
- Full `dashboard/tests` suite — see the completion report for the exact final count (run as its own process, same as Task 1, to avoid the environment's known combined-suite memory-limit issue).

## Live Validation

Performed with a temporary, isolated `ROLE_OS_WORKSPACE_DB_PATH` (a fresh `tempfile.mkdtemp()` path, never the real `var/role_os_dashboard/role_os_workspace.db`) — the same isolation pattern `dashboard/tests/conftest.py` uses for every test, applied here to a one-off interactive validation run instead of pytest. `ROLE_OS_DISCOVERY_ROOTS` was set to the repo's existing default root plus `C:\Users\rolev\Documents`.

- Roots scanned: 2 (both valid, no diagnostics — no invalid/duplicate/nested roots in this real configuration).
- Projects found: 53 (merged, deduplicated).
- Newly discoverable real projects: 6 (table above) plus every non-project `Documents` entry, correctly filtered by the existing classifier.
- Existing adopted projects: 0 in this isolated validation database (by design — it never touched the real one).
- Duplicates suppressed: 0 observed in this run (the two configured roots do not overlap or nest), verified programmatically not to happen even when they do (see Tests above).
- Errors/warnings: none — both configured roots existed, were directories, and were distinct.
- No `/workspace/{id}/adopt`, `/workspace/{id}/ignore`, note, or override call was made during validation. No file was written outside the temporary `tempfile.mkdtemp()` directory used for `ROLE_OS_WORKSPACE_DB_PATH`.

## Runtime Safety

- The real, canonical `var/role_os_dashboard/role_os_workspace.db` was never opened during this task's validation — every rescan performed to observe multi-root behavior used an isolated `ROLE_OS_WORKSPACE_DB_PATH` pointed at a `tempfile.mkdtemp()` directory, mirroring Task 1's own isolation discipline.
- `var/role_os_alpha/` was not read, modified, or referenced by any code in this task.
- No test or validation step adopted, ignored, annotated, or overrode any real or newly-discovered project.
- No canonical SQLite database was committed to git.

## Files Changed

- `dashboard/app/discovery/roots.py` — new: `resolve_roots()`, `RootsResolution`, `RootDiagnostic`.
- `dashboard/app/config.py` — new `Settings.get_discovery_roots()` method; no existing field removed or renamed.
- `dashboard/app/workspace/service.py` — `rescan()` rewritten to branch single-root (unchanged behavior, extracted into `_rescan_single_root()`) vs. multi-root (new); `get_summary()`'s no-cache-yet fallback now reports every configured root, not just the single legacy one.
- `dashboard/tests/test_discovery_roots.py` — new.
- `dashboard/tests/test_config.py` — 5 new tests.
- `dashboard/tests/test_workspace_service.py` — 8 new tests.
- `docs/PHASE_2_MULTI_ROOT_DISCOVERY.md` — this file.
- `CURRENT_STATE.md`, `NEXT_ACTIONS.md` — updated per Step 13.

No production code outside `dashboard/app/config.py`, `dashboard/app/discovery/roots.py` (new), and `dashboard/app/workspace/service.py` was changed. No canonical production default path changed. No UI/template file changed (per the plan's explicit "no new UI concept" scope).

## Known Limitations

- Configuration is environment-variable-only, per the approved plan (§6, §9) — there is no in-app settings control to add/remove a root without editing the environment and restarting. This was an explicit scope decision (avoid a new settings UI, avoid a new persisted concept), not an oversight.
- Nested-root detection is purely path-prefix-based; it does not account for symlinks or junctions that make two configured roots refer to the same physical location via different paths (the existing scanner already skips symlinked subdirectories during a scan, per `app/discovery/scanner.py: _safe_subdirs`, but a configured *root itself* being a symlink alias of another configured root is not specifically detected).
- `SUPER-FACIL` does not exist at its documented path as of this validation — flagged above, not resolved; Role should confirm whether it was moved, renamed, or the source document is stale. `bolsa-de-trabajo` was in the same state at the time of this validation, but was subsequently found to be a registry path error, not a missing project — see the update note above and `docs/PHASE_2_MISSION_CONTROL_DAILY_USE_REVIEW.md`.
- Which of the real, newly-discoverable projects (if any) should actually be added to `ROLE_OS_DISCOVERY_ROOTS` in Role's real running configuration, and whether any should subsequently be adopted, remains Role's decision — this task only builds and validates the capability, per `NEXT_ACTIONS.md`'s explicit "do not auto-adopt" instruction.

## Exact Next Task

Phase 2 — Mission Control Daily-Use Gap Check (`docs/ROLE_OS_2_PHASE_2_PLAN.md`, Task 2.2).
