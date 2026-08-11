"""Dashboard 2.0 (Sprint C2).

The single, additive service that assembles the executive Dashboard's
already-shaped summary. See `service.build_dashboard_summary` -- it
composes existing canonical services (`ProjectContext`,
`workspace.service`, `workspace.advisor`, `workspace.portfolio`, `app.db`)
rather than recomputing anything they already know how to compute.
"""

from __future__ import annotations

from app.dashboard.service import build_dashboard_summary

__all__ = ["build_dashboard_summary"]
