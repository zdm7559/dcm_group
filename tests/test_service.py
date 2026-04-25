from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from web_service.app import app


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_divide_normal(client: AsyncClient) -> None:
    response = await client.get("/divide", params={"a": 10, "b": 2})

    assert response.status_code == 200
    assert response.json() == {"result": 5.0}


async def test_divide_by_zero_should_return_400(client: AsyncClient) -> None:
    response = await client.get("/divide", params={"a": 10, "b": 0})

    assert response.status_code == 400
    assert response.json()["error"] == "division by zero"


async def test_user_found(client: AsyncClient) -> None:
    response = await client.get("/users/1")

    assert response.status_code == 200
    assert response.json() == {"id": 1, "name": "Alice"}


async def test_user_not_found_should_return_404(client: AsyncClient) -> None:
    response = await client.get("/users/999")

    assert response.status_code == 404
    assert response.json()["error"] == "user not found"
