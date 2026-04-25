from __future__ import annotations

from fastapi import APIRouter

from web_service.services.calculator import divide_numbers


router = APIRouter(tags=["calculator"])


@router.get("/divide")
async def divide(a: float, b: float) -> dict[str, float]:
    return {"result": divide_numbers(a, b)}
