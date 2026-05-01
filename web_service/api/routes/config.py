from __future__ import annotations

from fastapi import APIRouter

from web_service.services.config import read_required_api_key, read_timeout_seconds


router = APIRouter(prefix="/config", tags=["bug-cases"])


@router.get("/missing-api-key")
async def missing_api_key() -> dict[str, str]:
    return {"api_key": read_required_api_key()}


@router.get("/invalid-timeout")
async def invalid_timeout() -> dict[str, int]:
    return {"timeout": read_timeout_seconds()}
