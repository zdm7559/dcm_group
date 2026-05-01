from __future__ import annotations

from fastapi import APIRouter

from web_service.services.naming import get_user_name


router = APIRouter(prefix="/naming", tags=["bug-cases"])


@router.get("/unknown-function")
async def unknown_function() -> dict[str, str]:
    return {"name": get_user_name()}
