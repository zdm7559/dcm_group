from __future__ import annotations

from fastapi import APIRouter

from web_service.services.users import get_user_by_id


router = APIRouter(tags=["users"])


@router.get("/users/{user_id}")
async def get_user(user_id: int):
    import json
    from starlette.responses import Response
    user = get_user_by_id(user_id)
    if user is None:
        return Response(content=json.dumps({"error": "user not found"}), status_code=404, media_type="application/json")
    return user
