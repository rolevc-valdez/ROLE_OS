"""Work classification vocabulary (Phase 3 Task 2): domain, client, kind,
and the recognised `completed` status.

One small module so the application boundary (API models), the persistence
layer (`workspace.db`), and every engine that must skip completed work all
agree on the same words. Nothing here touches a database.

Semantics (see `docs/PHASE_3_TASK_2_CLASSIFICATION_STATUS.md`):

* `domain` -- one of four fixed top-level areas, or `None` (= unclassified,
  never guessed). Stored upper-case.
* `client_name` -- optional free text, only meaningful when domain is
  CLIENTES.
* `kind` -- `project` (default) or `tool`. Stored lower-case.
* `status` stays free text for backwards compatibility. Only `completed`
  gains meaning: it is a terminal state that is excluded from active
  recommendations. It is NOT the same as `archived` (parked), which keeps
  its existing "paused" treatment.
"""

from __future__ import annotations

from typing import Any

DOMAINS = ("KONTOOR", "UNGER", "ROLE PERSONAL", "CLIENTES")
DOMAIN_CLIENTES = "CLIENTES"

KINDS = ("project", "tool")
DEFAULT_KIND = "project"

STATUS_COMPLETED = "completed"


def normalize_domain(value: str | None) -> str | None:
    """`None`/blank -> `None` (unclassified). Otherwise a case-insensitive
    match against `DOMAINS` (underscores/extra spaces tolerated); anything
    else raises `ValueError` -- never coerced to a nearest guess."""
    if value is None:
        return None
    cleaned = " ".join(str(value).replace("_", " ").split()).upper()
    if not cleaned:
        return None
    if cleaned not in DOMAINS:
        raise ValueError(f"domain must be one of {', '.join(DOMAINS)} (got {value!r})")
    return cleaned


def normalize_kind(value: str | None) -> str:
    """Blank/`None` -> the default (`project`); unknown values raise."""
    if value is None or not str(value).strip():
        return DEFAULT_KIND
    cleaned = str(value).strip().lower()
    if cleaned not in KINDS:
        raise ValueError(f"kind must be one of {', '.join(KINDS)} (got {value!r})")
    return cleaned


def normalize_client_name(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(str(value).split())
    return cleaned or None


def check_client_for_domain(domain: str | None, client_name: str | None) -> None:
    """A client name only makes sense under CLIENTES."""
    if client_name is not None and domain != DOMAIN_CLIENTES:
        raise ValueError("client_name is only allowed when domain is CLIENTES")


def is_completed_status(status: Any) -> bool:
    return isinstance(status, str) and status.strip().lower() == STATUS_COMPLETED


def is_rank_excluded(entity: dict[str, Any]) -> bool:
    """True for anything that must not compete in the active work ranking
    ("What should I do now?"): completed work, and reusable tools (Phase 3
    Task 3 -- tools live in the TOOLS area, they are not work to be done).
    Works on both enriched workspace items (`status`) and ProjectContexts
    (`is_completed`); either signal is enough."""
    return (
        bool(entity.get("is_completed"))
        or is_completed_status(entity.get("status"))
        or entity.get("kind") == "tool"
    )
