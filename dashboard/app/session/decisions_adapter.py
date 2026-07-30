"""Adapter for surfacing recent ROLE Ecosystem decisions on the Session page.

ROLE OS's dashboard has no database or API relationship with the
`role-ecosystem` repository -- they are separate repositories on disk with
no guaranteed common location (different clones, different machines). This
module never guesses a path between them. It only reads `DECISION_LOG.md`
live when the user explicitly points at it via the
`ROLE_OS_ECOSYSTEM_DECISION_LOG_PATH` environment variable; otherwise it
returns a small, explicitly-labeled fallback snapshot rather than either
crashing or duplicating the full log into this codebase.

This keeps the same seam every other cross-boundary read in this app
uses: a plain function with a documented, honest degradation path (see
`app/settings` for the equivalent pattern with git commit lookup).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings

# A small, explicitly-labeled snapshot of real entries from
# `role-ecosystem/DECISION_LOG.md` as of 2026-07-30, used only when live
# reading isn't configured or fails. This is deliberately NOT the full
# log (see that file for the complete, authoritative history with Context
# and Rationale) -- just enough to make the Session page's "Recent
# ecosystem decisions" card honest and useful without a live connection.
FALLBACK_DECISIONS: tuple[dict[str, str], ...] = (
    {
        "id": "D-005",
        "date": "2026-07-30",
        "decision": "Add ROLE Commerce Factory to ROADMAP.md Phase 4 and mark that phase Active.",
        "status": "Accepted",
    },
    {
        "id": "D-004",
        "date": "2026-07-30",
        "decision": "Retroactively formalize ROLE Commerce Factory's Definition-stage documentation.",
        "status": "Accepted",
    },
    {
        "id": "D-003",
        "date": "2026-07-29",
        "decision": "Adopt a strict Required Document Structure for every substantive document in the repository.",
        "status": "Accepted",
    },
    {
        "id": "D-002",
        "date": "2026-07-29",
        "decision": "Structure the roadmap as six sequential phases rather than calendar-dated milestones.",
        "status": "Accepted",
    },
    {
        "id": "D-001",
        "date": "2026-07-29",
        "decision": "Establish role-ecosystem as a documentation-only repository governing all ROLE products.",
        "status": "Accepted",
    },
)

_TABLE_ROW_RE = re.compile(
    r"^\|\s*(?P<id>D-\d+)\s*\|\s*(?P<date>[\d-]+)\s*\|\s*(?P<decision>.+?)\s*\|\s*(?P<status>\w+)\s*\|",
)


def _parse_decision_log(text: str) -> list[dict[str, str]]:
    """Parses the `## Log` table's ID/Date/Decision/Status columns only --
    Context and Rationale are intentionally not extracted here, so this
    adapter cannot become a second copy of the full log.
    """
    entries: list[dict[str, str]] = []
    in_log_section = False
    for line in text.splitlines():
        if line.strip().startswith("## Log"):
            in_log_section = True
            continue
        if in_log_section and line.strip().startswith("## "):
            break  # reached the next section
        if not in_log_section:
            continue
        match = _TABLE_ROW_RE.match(line.strip())
        if match:
            entries.append(
                {
                    "id": match.group("id"),
                    "date": match.group("date"),
                    "decision": match.group("decision"),
                    "status": match.group("status"),
                }
            )
    return entries


def read_recent_decisions(limit: int = 5, settings: Settings | None = None) -> dict[str, Any]:
    """Returns `{"decisions": [...], "source": "ecosystem"|"fallback", "note": str}`."""
    settings = settings or get_settings()
    path_str = settings.ecosystem_decision_log_path

    if not path_str:
        return {
            "decisions": list(FALLBACK_DECISIONS[:limit]),
            "source": "fallback",
            "note": (
                "ROLE_OS_ECOSYSTEM_DECISION_LOG_PATH is not set, so this is a "
                "documented fallback snapshot, not a live read. Set that "
                "environment variable to role-ecosystem/DECISION_LOG.md's "
                "path to read it live."
            ),
        }

    path = Path(path_str)
    if not path.exists():
        return {
            "decisions": list(FALLBACK_DECISIONS[:limit]),
            "source": "fallback",
            "note": f"ROLE_OS_ECOSYSTEM_DECISION_LOG_PATH ({path}) does not exist; showing a documented fallback snapshot instead.",
        }

    try:
        text = path.read_text(encoding="utf-8")
        parsed = _parse_decision_log(text)
    except OSError as exc:
        return {
            "decisions": list(FALLBACK_DECISIONS[:limit]),
            "source": "fallback",
            "note": f"Could not read {path} ({exc}); showing a documented fallback snapshot instead.",
        }

    if not parsed:
        return {
            "decisions": list(FALLBACK_DECISIONS[:limit]),
            "source": "fallback",
            "note": f"No decision rows found in {path}'s Log table; showing a documented fallback snapshot instead.",
        }

    return {
        "decisions": parsed[:limit],
        "source": "ecosystem",
        "note": f"Read live from {path}.",
    }
