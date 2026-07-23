"""Shared, dependency-free helpers used by multiple extractors.

Not an extractor itself — kept out of the public extractor set so the
package's extractor modules (summary, decisions, todos, prompts, entities,
relationships) stay one-responsibility-per-file.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Iterable

URL_RE = re.compile(r"https?://[^\s)\]}>\"']+")


def norm(text: str) -> str:
    """Lowercase and collapse whitespace for keyword matching."""
    return re.sub(r"\s+", " ", text.lower()).strip()


def to_iso(value) -> str:
    """Convert a Unix timestamp (as found in ChatGPT exports) to ISO-8601 UTC."""
    if not value:
        return ""
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return ""


def sentences(text: str) -> list[str]:
    """Split conversation body text into candidate sentence/line fragments."""
    lines = [re.sub(r"^[\-*•\d.\s]+", "", x).strip() for x in text.splitlines()]
    return [x for x in lines if 10 <= len(x) <= 500]


def pick(lines: Iterable[str], patterns: Iterable[str], limit: int = 10) -> list[str]:
    """Return up to `limit` unique lines matching any of the given regex patterns."""
    rx = re.compile("|".join(patterns), re.I)
    out: list[str] = []
    for line in lines:
        if rx.search(line) and line not in out:
            out.append(line)
            if len(out) >= limit:
                break
    return out
