from __future__ import annotations


def load_public_resource(resource_id: str) -> dict[str, str]:
    if resource_id != "welcome":
        raise ValueError("resource not found")
    return {"id": resource_id, "title": "Welcome"}
