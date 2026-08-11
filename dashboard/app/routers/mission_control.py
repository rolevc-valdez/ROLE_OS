"""Mission Control API (Sprint C5) -- namespaced under `/mission-control`.

One endpoint returning the daily operating surface's entire, already-shaped
payload -- see `app.mission_control.service.build_mission_control` for what
it composes and why no new ranking engine exists here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.mission_control.service import build_mission_control

router = APIRouter(prefix="/mission-control", tags=["mission-control"])


@router.get("")
def get_mission_control(settings: Settings = Depends(get_settings)) -> dict:
    return build_mission_control(settings=settings)
