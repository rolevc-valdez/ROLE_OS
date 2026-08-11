"""Executive Decision API (Sprint C10) -- namespaced under
`/executive-decision`, `api.py` living inside the package itself
(matching Sprint C9's `app.impact_analysis` deviation from the
`app/routers/`-per-domain convention).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.assets.service import request_scope
from app.config import Settings, get_settings
from app.executive_decision.service import get_executive_decision

router = APIRouter(prefix="/executive-decision", tags=["executive-decision"])


@router.get("")
def get_decision(settings: Settings = Depends(get_settings)) -> dict:
    with request_scope():
        return get_executive_decision(settings=settings)
