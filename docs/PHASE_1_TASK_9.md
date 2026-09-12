# Role OS 2.0 — Phase 1 Task 9

## Objective

Resolve the ambiguity around `var/discovery_reports/` — generated report artifacts flagged since the Phase 0 audit as having no obvious current consumer — with evidence first, cleanup second.

## Artifact Inventory

Exactly 2 files, one directory level deep: `var/discovery_reports/documents/documents_audit.json` (79,743 bytes) and `documents_audit.md` (6,771 bytes). Both dated **2026-07-31 12:55:00** (same second — one single report-writing event, not an accumulating cache). Both untracked, matched by the blanket `var/` rule in `.gitignore` (line 21) — never at risk of accidental commit. Both are clearly machine-generated (structured JSON; a Markdown report with computed summary tables) — no hand-edited or free-form prose found in either.

## Producers

`dashboard/app/discovery/__main__.py` — a documented, argparse-based CLI (`python -m app.discovery audit --root <path> --output <path> --basename <name>`), explicitly designed as a **manual, read-only audit tool**: it reuses `discovery/service.py: run_audit()` (the exact same Discovery Engine the FastAPI app uses for its normal scans) and `discovery/reporters.py: write_reports()` to render JSON + Markdown. It refuses to write inside the scanned `--root` (a safety check in `main()`). **Not invoked by the FastAPI runtime, any router, any launcher script, or any scheduled job** — confirmed by repository-wide search; the only way these two files could have been produced is someone running this CLI by hand once, with `--root "C:\Users\rolev\Documents" --output var/discovery_reports/documents --basename documents_audit` (the exact basename and content match). Configurable output path: yes, via `--output`.

## Consumers

**NONE** in application code, any router, any script, or any test that reads these specific *output files*. Classification: **NONE** (for the generated files themselves). The generation *mechanism* (`reporters.py`, `__main__.py`), however, has real, active test consumers: `dashboard/tests/test_discovery.py: test_reports_written_outside_root_only` and `dashboard/tests/test_discovery_boundary.py: test_boundary_fields_serialize_via_json_report` — classification **TEST**. No documentation references the specific output files as something to read regularly; a few historical docs (the audit, `PHASE_1_BASELINE.md`, the architecture proposal) merely *mention* this directory's existence — classification **HISTORICAL**.

## Semantic Classification

**DERIVED REPORT / EXPORT** — computed once from a live filesystem read (via the same Discovery Engine that backs canonical Role OS state), rendered into a human-readable snapshot. Not **AUTHORITATIVE STATE** (Role OS's real project truth stays in `adopted_projects`/Discovery's live re-scan, never this file). Not **CACHE** (nothing re-reads or invalidates it; it's not a performance optimization). Not **DEBUG OUTPUT** (it's a polished, user-facing report format, not a diagnostic dump). Read carefully, its *content* turned out to have real, otherwise-uncaptured informational value — see Unique Information Check below.

## Reproducibility

**Mechanically: yes.** Verified directly: ran `python -m app.discovery audit --root <isolated tmp dir> --output <isolated tmp dir> --basename regen_test` and got the identical JSON/Markdown structure (same headings, same summary-table shape, same schema) as the original report, proving the tool works today exactly as it did on 2026-07-31. Test used a synthetic, isolated `tmp` source tree and output directory — nothing in the repository or canonical runtime was touched or read for this check, and the temporary files were deleted immediately after.

**The specific content: no, not by default.** Role OS's Discovery Engine never scans `C:\Users\rolev\Documents` on its own (its default root is `1 - IA PROJECTS`'s parent) — reproducing *this exact report's findings* requires deliberately re-running the CLI against `Documents` again, which nothing does automatically. This distinction — "the tool is reproducible, the specific audit result is not, without deliberate re-invocation" — is exactly why this task did not just delete the files as "obviously regenerable."

## Unique Information Check

**YES — unique, otherwise-uncaptured information found.** The `Documents` audit surfaced several real, git-repository-backed projects that appear **nowhere else** in any canonical Role OS data or prior task doc: `SUPER-FACIL` (health 50, high move risk — 6 hardcoded absolute-path references), `AGUA-AZUL-APP`/`agua-azul-app` (health 37, a likely redundant wrapper folder), `charcos-site` (health 37), `desierto-creativo-site` (health 46). It also independently corroborates `role-content-factory` and `rolevaldez.com` — both already flagged in `docs/PHASE_1_TASK_6.md` as real, un-adopted projects living outside the Discovery root, found there via `project-dashboard.html`'s legacy catalog. None of this is in `adopted_projects`, `var/role_os_alpha/`, Git, or any existing doc except this report. **Per this task's explicit instruction: not deleted.**

## discovery/reporters.py Disposition

**KEEP AS MANUAL EXPORT.** It is well-designed (pure rendering functions over an existing `ScanResult`, no filesystem access except the one documented `write_reports` helper, an explicit safety check preventing writes inside the scanned root), actively tested, and reuses the canonical Discovery Engine rather than duplicating it. It fills a real, distinct role from the web app's automatic scanning: letting a person audit *any* folder on demand, including ones Role OS's normal operation never touches. No code change made or needed.

## Final Artifact Policy

**C — ARCHIVE**, applied specifically to the two existing output files; the generation mechanism itself is **A — KEEP** (as a manual, on-demand export tool, not a "runtime component" needing a runtime policy). Reasoning: the files contain real, unique, non-default-reproducible information (ruling out B/"no unique information" or simple deletion), but leaving them inside `var/` — a directory this whole Phase 1 effort has consistently treated as ephemeral, regenerable, and git-ignored — risks exactly the kind of silent, easily-lost, easily-misunderstood state Phase 1 has been eliminating everywhere else. Archiving (matching the `archive/legacy-dashboard/` precedent from Task 6) makes its historical, preserved status explicit and durable (git-tracked) rather than implicit and fragile (gitignored, one `var/` wipe away from gone).

## Cleanup Performed

1. Recorded SHA256 checksums of both files before moving: `documents_audit.json` = `14b145f5...bffb38`; `documents_audit.md` = `fdc846c6...b697a17`.
2. Moved both files (not copied-then-deleted) to `archive/discovery-reports/documents-2026-07-31/`, preserving original mtimes.
3. Verified SHA256 checksums identical post-move (byte-for-byte, confirmed).
4. Removed the now-empty `var/discovery_reports/documents/` and `var/discovery_reports/` directories (`rmdir`, which only succeeds on genuinely empty directories — nothing was force-deleted).
5. Wrote `archive/discovery-reports/README.md` explaining what the reports are, why archived, when, and confirming the generation capability remains fully available.

## Git / Ignore Policy

`var/discovery_reports/` remains covered by the existing blanket `var/` ignore rule (`.gitignore` line 21) — appropriate, since any *future* run of this CLI produces exactly the kind of ephemeral, regenerable-on-demand output that pattern is meant to exclude. `archive/discovery-reports/` (new) is **not** ignored — it is deliberately git-tracked, exactly like `archive/legacy-dashboard/`. No `.gitignore` change was needed; the existing rule already does the right thing for both cases.

## Validation

No application code changed (`reporters.py`, `__main__.py` untouched — confirmed via `git diff --stat`), so no new application tests were written, per this task's own "do not invent unnecessary tests" instruction. Validation performed instead:
- Isolated regeneration test (above) — confirmed the mechanism still works, using only temporary, non-repository paths.
- `sha256sum` before and after the archive move — confirmed byte-for-byte integrity.
- Repository-wide search for `discovery_reports` — confirmed zero active code consumers exist to break; only historical/doc mentions remain, none of which are rewritten (per "do not rewrite unrelated sections").
- `dashboard/tests/test_discovery.py` and `test_discovery_boundary.py`'s existing coverage of `reporters.py`/`write_reports` was not touched and remains valid, since no source code changed.

## Files Changed

- `archive/discovery-reports/README.md` — new
- `archive/discovery-reports/documents-2026-07-31/documents_audit.json` — new (moved, byte-identical)
- `archive/discovery-reports/documents-2026-07-31/documents_audit.md` — new (moved, byte-identical)
- `var/discovery_reports/` — removed (was empty after the move; not git-tracked, so this is not a "deleted files" event in git's history)
- `docs/RUNTIME_DATA_MAP.md` — one table cell updated, one new section added
- `docs/PHASE_1_TASK_9.md` — this file

No application source code changed.

## Remaining Risks / Decisions

- The newly-surfaced real projects (`SUPER-FACIL`, `AGUA-AZUL-APP`, `charcos-site`, `desierto-creativo-site`) are, like `role-content-factory`/`rolevaldez.com` before them, outside Role OS's default Discovery scope and not adopted. This task does not adopt them (explicitly out of scope: "do not perform unrelated cleanup") — it only ensures the information that revealed them is preserved rather than lost. Folded into `CURRENT_STATE.md`'s existing "real projects outside the Discovery root" open item rather than creating a new one.
- No other `var/`-resident artifact directory was found needing the same treatment during this task's repository-wide search — `var/discovery_reports/` was the only one of its kind.

## Phase 1 Readiness

With Task 9 closed, every task explicitly scoped for Phase 1 (Tasks 1 through 9) is complete. Phase 1 — Final Validation / Completion Review is next; this task did not begin it.
