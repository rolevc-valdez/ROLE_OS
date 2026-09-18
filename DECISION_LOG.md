# Decision Log

**Version:** 1.0
**Status:** Active
**Owner:** Rogelio (Role Valdez)

## Purpose

This document is the permanent, append-only record of every significant decision made about the ROLE ecosystem: direction, scope, process, technology, and structure. It exists so that "why did we do it this way" always has a written answer instead of relying on memory.

## Scope

Covers ecosystem-level and cross-product decisions: changes to `VISION.md`, `ROADMAP.md`, `ARCHITECTURE_PRINCIPLES.md`, `PRODUCT_LIFECYCLE.md`, any file in `standards/`, or any decision that affects more than one product. Product-specific decisions that don't affect the rest of the ecosystem are logged inside that product's file in `projects/` instead, in the same format.

## Principles

- **Append, never rewrite.** A decision that turns out to be wrong is superseded by a new entry, not deleted or edited into something it wasn't.
- **Reasoning over record-keeping.** Every entry answers "why," not just "what."
- **One entry, one decision.** Do not bundle unrelated decisions into a single entry.

## Format

Each entry uses `templates/DECISION_TEMPLATE.md` and is appended to the **top** of the Log table below (most recent first). Every entry has:

| Field | Meaning |
|---|---|
| ID | Sequential identifier, `D-001`, `D-002`, ... |
| Date | ISO 8601 date the decision was made |
| Decision | One-sentence statement of what was decided |
| Status | `Proposed`, `Accepted`, `Superseded`, or `Reverted` |
| Context | The situation or problem that made a decision necessary |
| Rationale | Why this option was chosen over the alternatives |
| Supersedes | ID of a prior decision this replaces, if any |

## Process — Logging a Decision

1. Confirm the decision is ecosystem-level (this file) or product-level (that product's file in `projects/`).
2. Copy `templates/DECISION_TEMPLATE.md` and fill in every field — do not skip Rationale.
3. Assign the next sequential ID.
4. Add the entry to the top of the Log table below.
5. If this decision supersedes an earlier one, set that earlier entry's Status to `Superseded` and reference the new ID — never delete it.

## Log

| ID | Date | Decision | Status | Context | Rationale |
|---|---|---|---|---|---|
| D-008 | 2026-09-16 | Create the ecosystem category `ROLE HERRAMIENTAS PERSONALES` for external tools Role adopts for individual use, and register Cobalt as its first entry without treating it as a development project. | Accepted | Cobalt (`imputnet/cobalt`) was evaluated as a useful individual media-downloading tool. Recording it under Active Projects or integrating it into RoleSocialFactory would incorrectly turn a personal utility into project scope and would consume attention reserved for Role's maximum of two active projects. | The ecosystem must distinguish tools from projects and keep a single truthful index of what Role uses. A dedicated personal-tools category preserves visibility without creating code, repositories, integrations, maintenance obligations, or parallel sources of truth. |
| D-007 | 2026-07-30 | Release ROLE OS v1.1.0 (the Daily Session / ROLE OS Dashboard MVP) via `playbooks/RELEASE_PROCESS.md`, and move `projects/ROLE_OS.md`'s Current Lifecycle Stage from Build to Maintenance. | Accepted | Following `D-006`'s reconciliation, the Product half of ROLE OS was confirmed mid-Build with its version not yet bumped. This entry records the release itself: version bumped `1.0.0` → `1.1.0` everywhere it is defined (`pyproject.toml`, `dashboard/app/config.py`, `README.md`, and the two illustrative example-response snippets in `dashboard/README.md`), `CHANGELOG.md`'s `[Unreleased]` section closed to `[1.1.0] - 2026-07-30` with its content otherwise preserved verbatim, `RELEASE_NOTES_v1.1.0.md` published, and a git commit + annotated tag `v1.1.0` created. | `standards/VERSIONING.md`: classified MINOR (backward-compatible new feature, no breaking change) — confirmed by the Daily Session domain being additive-only with zero changes to any pre-existing endpoint, page, or database, and by the full test suite passing before and after the bump (464/464). `playbooks/RELEASE_PROCESS.md` step 11 ("Close the release... update the product's file in `projects/` with the new live version and Release-stage status") is the direct basis for updating `projects/ROLE_OS.md`'s Current Lifecycle Stage; Maintenance was chosen over Growth because ROLE OS has no `business/GO_TO_MARKET.md` adoption/revenue tracking to graduate into — it remains an internal tool, honestly reflected rather than overstated. |
| D-006 | 2026-07-30 | Rewrite `projects/ROLE_OS.md` to describe ROLE OS as both a Framework (daily operating methodology, session modes, project/decision discipline, governance conventions) and a Product (the Python/FastAPI application at `ROLE_OS/`: Builder CLI, Command Center dashboard, local SQLite persistence, Daily Session management, Obsidian-compatible records) — not one or the other. | Accepted | `projects/ROLE_OS.md` described ROLE OS as "infrastructure... not a product a customer ever sees directly" and its Current Lifecycle Stage as Maintenance. Neither was true: `ROLE_OS/` is a real, v1.0-released, actively-tested software product (464 passing tests) that had just gained a new Daily Session feature (the ROLE OS Dashboard MVP) still sitting `[Unreleased]` in its own `CHANGELOG.md` — meaning the product was genuinely in Build, not Maintenance, and was never "not a product." This gap was discovered when a PLAN-mode session was asked to reconcile the two before declaring the Dashboard MVP v1.1.0 complete. | `ARCHITECTURE_PRINCIPLES.md` Principle 1 (Documentation First) and Principle 8 (Continuous Improvement): the ecosystem-level record must describe what is actually true, not what was true when the file was first written. The rewrite preserves ROLE OS as "the operating layer of the ROLE ecosystem" (Principle 2, Single Source of Truth was not violated — the Product's own architecture is summarized, not duplicated, with `ROLE_OS/ARCHITECTURE.md` etc. remaining authoritative) while correcting Current Lifecycle Stage to Build and adding Architecture, Major Components, Dependencies, and a Definition of Done section per this task's explicit requirements. `ROADMAP.md` was reviewed and required no change — it already listed ROLE OS as an active Phase 1 product with "documented and operational" as its exit criteria, which this reconciliation confirms progress toward rather than contradicts. |
| D-005 | 2026-07-30 | Add `ROLE Commerce Factory` to `ROADMAP.md` Phase 4 — Products, and change Phase 4's status from ⚪ Planned to 🟢 Active. | Accepted | Following `D-004`, `ROLE Commerce Factory` now has a `projects/` entry showing it is already in the Build stage of `PRODUCT_LIFECYCLE.md`, with two working adapters. `ROADMAP.md` previously listed Phase 4 as Planned and did not mention this product at all, which no longer matched reality. | `ARCHITECTURE_PRINCIPLES.md` Principle 8 (Continuous Improvement) and `ROADMAP.md`'s own Best Practices ("a roadmap that lags reality is worse than no roadmap"); `ROADMAP.md` Principles already permit a later phase (here, Phase 4) to be underway before every earlier phase's exit criteria are fully met, provided the specific dependency is satisfied — Phase 4's Dependencies line was updated in the same change to name Phase 3 – Automation as the specific blocker for this product's orchestration layer, not for the adapters already working. |
| D-004 | 2026-07-30 | Create the missing `projects/ROLE_COMMERCE_FACTORY.md` entry and this product's full Definition-stage documentation set (PRD, architecture, roadmap, decision log, repository README), retroactively, for a product whose Build-stage code already existed. | Accepted | `ROLE Commerce Factory` (containing `RCOM-Printful-Adapter` and `RCOM-Shopify-Adapter`, both with working, tested code) had no file in `projects/` and no PRD — a direct violation of `PRODUCT_LIFECYCLE.md`'s Definition-stage gate and `ARCHITECTURE_PRINCIPLES.md` Principle 1, discovered during ecosystem initialization against `SYSTEM.md`. | Principle 1 (Documentation First) and Principle 8 (Continuous Improvement): the gap is corrected by documenting the product's real, current state rather than discarding working code or leaving the gap unrecorded. The product's own repository structure also deviates from `standards/REPOSITORY_STRUCTURE.md` (multiple independent packages under one product folder) and its folder name deviates from `standards/NAMING.md`; both deviations are logged explicitly, not silently absorbed, in `ROLE Commerce Factory/Documentation/DECISION_LOG.md` entry `RCOM-D-003` and in `projects/ROLE_COMMERCE_FACTORY.md`'s Checklist. |
| D-003 | 2026-07-29 | Adopt a strict Required Document Structure (Purpose, Scope, Principles, Process, Best Practices, Checklist, References) for every substantive document in the repository. | Accepted | The repository was growing with inconsistent, one-line documents that gave no reader (human or AI) a reliable structure to expect. | Consistency Over Complexity and Documentation First both require predictable structure; a fixed section set lets any document be authored or audited against the same checklist, defined in `DOCUMENTATION_STANDARD.md`. |
| D-002 | 2026-07-29 | Structure the roadmap as six sequential phases (Foundation, Creation, Automation, Products, Business, Platform) rather than calendar-dated milestones. | Accepted | Ecosystem products depend heavily on each other's infrastructure; a date-based roadmap would create false urgency on phases whose real dependency is completeness, not time. | Dependency-based sequencing keeps `ROADMAP.md` honest about what is actually blocking what, per the Scalability and Continuous Improvement principles. |
| D-001 | 2026-07-29 | Establish `role-ecosystem` as a documentation-only repository governing all current and future ROLE products, separate from any product's own source code repository. | Accepted | Product work was starting without a shared reference for process, naming, or standards, causing each product to re-derive conventions independently. | Single Source of Truth requires one authoritative place for cross-product rules; keeping it documentation-only (no source code) keeps its scope unambiguous, per `ARCHITECTURE_PRINCIPLES.md`. |

## Best Practices

- Write the Context field as if the reader has no memory of the situation — because eventually, they won't.
- Log a decision at the time it's made, not retroactively from memory weeks later.
- When in doubt whether something is "significant enough" to log, log it — a short entry costs little; a missing one costs a repeated debate later.

## Checklist — Before Logging a Decision

- [ ] Decision is stated in one sentence
- [ ] Context explains the situation without assuming prior knowledge
- [ ] Rationale references the principle(s) in `ARCHITECTURE_PRINCIPLES.md` that justified the choice
- [ ] ID is sequential and unique
- [ ] Any superseded entry has been updated, not deleted

## References

- `templates/DECISION_TEMPLATE.md` — the skeleton used for each entry
- `ARCHITECTURE_PRINCIPLES.md` — the principles decisions are justified against
- `ROADMAP.md`, `VISION.md`, `PRODUCT_LIFECYCLE.md` — the documents most decisions in this log affect
