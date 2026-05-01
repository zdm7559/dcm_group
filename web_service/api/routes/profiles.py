from __future__ import annotations

from fastapi import APIRouter

from web_service.services.profiles import get_profile_name


router = APIRouter(prefix="/data", tags=["bug-cases"])


@router.get("/missing-profile")
async def missing_profile() -> dict[str, str]:
    return {"name": get_profile_name(999)}
