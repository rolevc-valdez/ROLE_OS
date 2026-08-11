"""Dashboard 2.0 API (Sprint C2) -- namespaced under `/dashboard`.

One additive endpoint returning the executive Dashboard's entire,
already-shaped summary -- see `app.dashboard.service.build_dashboard_
summary` for what it composes and why no new aggregation engine exists
here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.dashboard.service import build_dashboard_summary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def get_dashboard_summary(settings: Settings = Depends(get_settings)) -> dict:
    return build_dashboard_summary(settings=settings)
