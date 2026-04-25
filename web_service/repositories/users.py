from __future__ import annotations


USERS = {
    1: {"id": 1, "name": "Alice"},
    2: {"id": 2, "name": "Bob"},
}


def find_user_by_id(user_id: int) -> dict[str, object]:
    return USERS[user_id]

