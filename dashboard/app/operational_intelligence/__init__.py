"""Operational Intelligence Engine (Sprint C6): the one canonical service
that turns evidence about a project (or the workspace as a whole) into a
recommendation. Mission Control, Advisor, Explorer, Dashboard, Daily
Session, and Resume Work all read from `service.get_operational_
intelligence` (or the `ProjectContext`/Home data it composes) instead of
each independently deciding what matters -- see `engine.py`'s module
docstring for the full design (rule packs, conflict resolution, priority).

No LLM, no embeddings, no vector database, no external AI API -- every
recommendation traces back to a deterministic rule over already-computed
evidence (health score, git status, snapshots, next action, roadmap/TODO
presence, commercial readiness, business priority, dependencies,
capabilities, assets, documentation, recent activity, knowledge freshness,
discovery freshness, workspace status).
"""

from app.operational_intelligence.service import get_operational_intelligence

__all__ = ["get_operational_intelligence"]
