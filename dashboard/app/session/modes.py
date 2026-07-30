"""Operation mode configuration -- the single reusable source of truth for
every ROLE OS operation mode (PLAN, BUILD, CREATE, LAUNCH, OPERATE, LEARN).

This module is the one place a mode's name, purpose, expected AI behavior,
and primary ROLE Ecosystem resources are defined. The API (`app.routers.
session`) serves this list read-only at `GET /session/modes`; the Command
Center UI (`static/js/app.js`) fetches it from there rather than
hardcoding a second copy, so a mode never needs to be edited in two
places, per `ARCHITECTURE_PRINCIPLES.md`'s Single Source of Truth.
"""

from __future__ import annotations

from typing import TypedDict


class ModeDefinition(TypedDict):
    id: str
    name: str
    purpose: str
    ai_behavior: str
    resources: list[str]


MODES: list[ModeDefinition] = [
    {
        "id": "PLAN",
        "name": "Plan",
        "purpose": "Scope a problem, evaluate options, and decide direction before any code or content is produced.",
        "ai_behavior": (
            "Ask clarifying questions before proposing a direction; lay out "
            "trade-offs explicitly; do not write code or final copy -- "
            "produce a plan, a PRD outline, or a decision recommendation "
            "and stop for approval."
        ),
        "resources": [
            "VISION.md",
            "ROADMAP.md",
            "PRODUCT_LIFECYCLE.md",
            "templates/PRD_TEMPLATE.md",
        ],
    },
    {
        "id": "BUILD",
        "name": "Build",
        "purpose": "Implement a scoped, already-approved piece of work in an existing product's codebase.",
        "ai_behavior": (
            "Inspect the current repository before writing code; reuse "
            "existing structure and stack; implement the smallest correct "
            "change; wait for approval before destructive or architectural "
            "changes; run tests before claiming something works."
        ),
        "resources": [
            "PRODUCT_LIFECYCLE.md",
            "ARCHITECTURE_PRINCIPLES.md",
            "standards/CODING_STANDARDS.md",
            "standards/REPOSITORY_STRUCTURE.md",
            "projects/<PRODUCT>.md",
        ],
    },
    {
        "id": "CREATE",
        "name": "Create",
        "purpose": "Produce creative or brand assets -- content, characters, visuals, copy -- consistent with ROLE brand standards.",
        "ai_behavior": (
            "Follow existing brand and character standards before "
            "introducing new visual or verbal style; reuse established "
            "templates and prompt patterns; flag anything that would "
            "require a new brand rule instead of deciding one unilaterally."
        ),
        "resources": [
            "standards/BRAND_GUIDELINES.md",
            "projects/BRAND_CHARACTER_OS.md",
            "projects/CONTENT_FACTORY.md",
        ],
    },
    {
        "id": "LAUNCH",
        "name": "Launch",
        "purpose": "Ship a product or release to real users: release notes, go-to-market steps, and release-stage gates.",
        "ai_behavior": (
            "Follow the release playbook exactly rather than improvising "
            "steps; confirm QA and lifecycle-stage exit criteria are met "
            "before treating anything as shipped; produce the required "
            "release artifact (changelog, release note)."
        ),
        "resources": [
            "PRODUCT_LIFECYCLE.md",
            "playbooks/RELEASE_PROCESS.md",
            "playbooks/FIRST_RELEASE.md",
            "business/GO_TO_MARKET.md",
        ],
    },
    {
        "id": "OPERATE",
        "name": "Operate",
        "purpose": "Keep a released, stable product healthy at low cost: triage, small fixes, and day-to-day upkeep.",
        "ai_behavior": (
            "Prefer the smallest fix that resolves the reported issue; do "
            "not restructure working code while operating; log operational "
            "notes rather than letting them stay tribal knowledge."
        ),
        "resources": [
            "playbooks/DAILY_PRODUCT_LOG.md",
            "playbooks/RELEASE_PROCESS.md",
            "projects/<PRODUCT>.md",
        ],
    },
    {
        "id": "LEARN",
        "name": "Learn",
        "purpose": "Research, read, or synthesize knowledge without committing to a build or ship decision yet.",
        "ai_behavior": (
            "Prioritize accurate synthesis over speed; cite where a claim "
            "came from; explicitly separate what was found from what is "
            "being recommended; do not write production code."
        ),
        "resources": [
            "VISION.md",
            "DECISION_LOG.md",
            "docs/architecture/",
            "docs/product/DECISIONS.md",
        ],
    },
]

_MODES_BY_ID: dict[str, ModeDefinition] = {mode["id"]: mode for mode in MODES}


def list_modes() -> list[ModeDefinition]:
    return MODES


def get_mode(mode_id: str) -> ModeDefinition | None:
    return _MODES_BY_ID.get(mode_id.upper())


def is_valid_mode(mode_id: str) -> bool:
    return mode_id.upper() in _MODES_BY_ID
