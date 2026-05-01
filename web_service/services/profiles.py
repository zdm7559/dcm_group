from __future__ import annotations


class UserProfile:
    def __init__(self, user_id: int, display_name: str) -> None:
        self.user_id = user_id
        self.display_name = display_name


def find_profile(user_id: int) -> UserProfile | None:
    if user_id == 1:
        return UserProfile(user_id=1, display_name="Alice")
    return None


def get_profile_name(user_id: int) -> str:
    profile = find_profile(user_id)
    return profile.display_name
