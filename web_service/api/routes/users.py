from __future__ import annotations

from fastapi import APIRouter

from web_service.services.users import get_user_by_id


router = APIRouter(tags=["users"])


@router.get("/users/{user_id}")
async def get_user(user_id: int):
    from fastapi.responses import JSONResponse

    user = get_user_by_id(user_id)
    if user is None:
        return JSONResponse(status_code=404, content={"error": "user not found"})
    return user
