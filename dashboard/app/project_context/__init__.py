"""ProjectContext (Sprint C1: Consolidation).

The single, authoritative service for assembling everything the UI needs
to describe one project -- see `builder.py`'s module docstring for the
architecture. Every page (Home, Projects, Cockpit, Advisor, Workspace) is
meant to request this same object rather than each independently
reassembling a subset of it from Discovery/Workspace/Project Intelligence/
Advisor.
"""

from __future__ import annotations

from app.project_context.builder import build_project_context, build_project_contexts_for_workspace

__all__ = ["build_project_context", "build_project_contexts_for_workspace"]
