from __future__ import annotations

from fastapi import APIRouter

from web_service.services.resources import load_public_resource


router = APIRouter(prefix="/resources", tags=["bug-cases"])


@router.get("/not-found-as-500")
async def not_found_as_500() -> dict[str, str]:
    return load_public_resource("missing")
