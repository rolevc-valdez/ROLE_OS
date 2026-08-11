"""Public entry point -- `app.operational_intelligence.get_operational_
intelligence` re-exports this. A separate module from `engine.py` only so
callers import a stable, short path (`app.operational_intelligence.
service`) without needing to know the engine's internal module layout.
"""

from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.operational_intelligence.engine import generate_recommendations


def get_operational_intelligence(
    settings: Settings | None = None,
    *,
    all_contexts: list[dict[str, Any]] | None = None,
    enriched_items: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    return generate_recommendations(
        settings=settings or get_settings(),
        all_contexts=all_contexts,
        enriched_items=enriched_items,
    )
