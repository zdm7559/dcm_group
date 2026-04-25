from __future__ import annotations

from fastapi import APIRouter

from web_service.services.users import get_user_by_id


router = APIRouter(tags=["users"])


@router.get("/users/{user_id}")
def get_user(user_id: int) -> dict[str, object]:
    return get_user_by_id(user_id)

