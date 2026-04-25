from __future__ import annotations

from fastapi.testclient import TestClient

from web_service.app import app


client = TestClient(app, raise_server_exceptions=False)


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_divide_normal() -> None:
    response = client.get("/divide", params={"a": 10, "b": 2})

    assert response.status_code == 200
    assert response.json() == {"result": 5.0}


def test_divide_by_zero_should_return_400() -> None:
    response = client.get("/divide", params={"a": 10, "b": 0})

    assert response.status_code == 400
    assert response.json()["error"] == "division by zero"


def test_user_found() -> None:
    response = client.get("/users/1")

    assert response.status_code == 200
    assert response.json() == {"id": 1, "name": "Alice"}


def test_user_not_found_should_return_404() -> None:
    response = client.get("/users/999")

    assert response.status_code == 404
    assert response.json()["error"] == "user not found"

