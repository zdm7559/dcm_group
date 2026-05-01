from __future__ import annotations

from fastapi import APIRouter, Request

from web_service.services.requests import parse_json_body


router = APIRouter(prefix="/request", tags=["bug-cases"])


@router.post("/invalid-json")
async def invalid_json(request: Request) -> dict[str, object]:
    raw_body = (await request.body()).decode("utf-8")
    return {"data": parse_json_body(raw_body)}
