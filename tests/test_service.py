from __future__ import annotations

import shutil
from pathlib import Path

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


async def test_invalid_json_should_return_400(client: AsyncClient) -> None:
    response = await client.post(
        "/request/invalid-json",
        content="{bad json}",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 400


async def test_missing_config_should_not_return_500(client: AsyncClient) -> None:
    response = await client.get("/files/missing-config")

    assert response.status_code in {200, 404}


async def test_missing_log_dir_should_create_directory(client: AsyncClient) -> None:
    log_dir = Path("logs/missing-dir")
    shutil.rmtree(log_dir, ignore_errors=True)

    response = await client.get("/files/missing-log-dir")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert (log_dir / "app.log").exists()


async def test_missing_api_key_should_return_client_or_service_error(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("API_KEY", raising=False)

    response = await client.get("/config/missing-api-key")

    assert response.status_code in {400, 503}


async def test_invalid_timeout_should_return_400(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TIMEOUT", "abc")

    response = await client.get("/config/invalid-timeout")

    assert response.status_code == 400


async def test_missing_yaml_should_not_return_500(client: AsyncClient) -> None:
    response = await client.get("/dependencies/missing-yaml")

    assert response.status_code in {200, 503}


async def test_bad_import_should_not_return_500(client: AsyncClient) -> None:
    response = await client.get("/dependencies/bad-import")

    assert response.status_code in {200, 400, 404}


async def test_unknown_function_should_return_200(client: AsyncClient) -> None:
    response = await client.get("/naming/unknown-function")

    assert response.status_code == 200
    assert isinstance(response.json()["name"], str)


async def test_missing_profile_should_return_404(client: AsyncClient) -> None:
    response = await client.get("/data/missing-profile")

    assert response.status_code == 404


async def test_not_found_resource_should_return_404(client: AsyncClient) -> None:
    response = await client.get("/resources/not-found-as-500")

    assert response.status_code == 404
