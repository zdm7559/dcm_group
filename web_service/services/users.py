from __future__ import annotations

from web_service.repositories.users import find_user_by_id


def get_user_by_id(user_id: int) -> dict[str, object]:
    return find_user_by_id(user_id)

