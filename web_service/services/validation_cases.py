from __future__ import annotations

from datetime import datetime
from typing import Any


DEMO_USERS = {
    "alice": {"id": "alice", "email": "alice@example.com"},
    "missing-email": {"id": "missing-email", "email": None},
}


def build_profile_from_required_params(params: dict[str, str]) -> dict[str, object]:
    return {
        "name": params["name"],
        "age": int(params["age"]),
    }


def parse_age_param(params: dict[str, str]) -> dict[str, int]:
    return {"age": int(params["age"])}


def query_page(params: dict[str, str]) -> dict[str, object]:
    page = int(params["page"])
    limit = int(params["limit"])
    offset = (page - 1) * limit
    records = ["alpha", "beta", "gamma"]
    return {
        "page": page,
        "limit": limit,
        "items": records[offset : offset + limit],
        "page_count": len(records) // limit,
    }


def normalize_username(params: dict[str, str]) -> dict[str, str]:
    username = params["username"].strip()
    return {"username": username[0].lower() + username[1:]}


def find_user(user_id: str) -> dict[str, Any] | None:
    return DEMO_USERS.get(user_id)


def get_missing_user_email() -> dict[str, str]:
    user = find_user("not-exists")
    return {"email": user["email"].lower()}


def get_none_email_lowercase() -> dict[str, str]:
    user = find_user("missing-email")
    return {"email": user["email"].lower()}


def read_age_from_body(data: dict[str, Any]) -> dict[str, int]:
    return {"age": int(data["age"])}


def convert_int_value(value: str) -> dict[str, int]:
    return {"value": int(value)}


def convert_float_value(value: str) -> dict[str, float]:
    return {"value": float(value)}


def parse_date_value(value: str) -> dict[str, str]:
    parsed = datetime.strptime(value, "%Y-%m-%d")
    return {"date": parsed.date().isoformat()}
