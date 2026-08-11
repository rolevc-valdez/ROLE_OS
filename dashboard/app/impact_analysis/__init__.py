"""Impact Analysis Engine (Sprint C9): answers "if this project changes,
what else is affected?" entirely from evidence the Project Ecosystem
Engine (Sprint C8), ProjectContext, and Operational Intelligence
(Sprint C6) already computed -- no new relationship detection, no new
graph, no LLM/embeddings/vector database.

`service.get_impact_analysis` is the one entry point every consumer (the
API in `api.py`, Explorer, Mission Control, Project Memory) reads from.
"""

from app.impact_analysis.service import get_impact_analysis

__all__ = ["get_impact_analysis"]
