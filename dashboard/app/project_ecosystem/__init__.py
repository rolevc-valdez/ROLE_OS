"""Project Ecosystem Engine (Sprint C8): understands how adopted projects
relate to each other -- dependencies, shared assets/knowledge/
documentation/prompts/sessions, and blocking relationships -- from
deterministic evidence only (no LLM, no embeddings, no vector database).

`service.get_project_ecosystem` is the one entry point every consumer
(the API, Explorer, Project Memory, Mission Control's Operational
Intelligence Engine) reads from; nothing downstream computes a
relationship independently. See `models.py` for the canonical
relationship shape, `detectors.py` for the evidence sources, `graph.py`
for the per-project view (dependencies/consumers/blocks/impact summary),
and `relationships.py` for conflict resolution + manual overrides.
"""

from app.project_ecosystem.service import compute_relationships, get_project_ecosystem

__all__ = ["compute_relationships", "get_project_ecosystem"]
