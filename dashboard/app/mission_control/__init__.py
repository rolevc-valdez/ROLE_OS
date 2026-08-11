"""Mission Control (Sprint C5): the daily operating surface of ROLE OS.

A composition layer only -- see `service.build_mission_control` for the one
entry point. Every field in its payload is produced by an existing service
(`ProjectContext`, `workspace.service`'s Home portfolio, the Workspace
Advisor, the Recent Activity feed, the Daily Session domain) called exactly
once; nothing here re-derives health, next action, ranking, or
recommendation priority.
"""

from app.mission_control.service import build_mission_control

__all__ = ["build_mission_control"]
