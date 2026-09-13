from __future__ import annotations

import httpx
import pytest
from fastapi import Body, Depends
from sss_api.config import ApiSettings
from sss_api.idempotency import require_idempotency_key
from sss_api.main import create_app
from sss_api.security import require_service_token


def _settings(*, max_body_bytes: int = 128) -> ApiSettings:
    return ApiSettings(
        environment="test",
        policy_version="policy-under-test",
        bearer_tokens=("test-token",),
        max_body_bytes=max_body_bytes,
        idempotency_key_max_bytes=128,
        sse_heartbeat_seconds=1,
        sse_buffer_size=8,
    )


@pytest.mark.asyncio
async def test_liveness_has_request_id() -> None:
    transport = httpx.ASGITransport(app=create_app(settings=_settings()))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json()["service"] == "sss-api"
    assert response.headers["X-Request-ID"]


@pytest.mark.asyncio
async def test_event_stream_requires_authentication() -> None:
    transport = httpx.ASGITransport(app=create_app(settings=_settings()))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/events")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_request_body_limit_rejects_oversized_payload() -> None:
    app = create_app(settings=_settings(max_body_bytes=8))

    @app.post("/echo")
    async def echo(payload: bytes = Body()) -> dict[str, int]:
        return {"size": len(payload)}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/echo", content=b"0123456789", headers={"Content-Type": "text/plain"}
        )

    assert response.status_code == 413


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "authorization",
    [None, "Basic test-token", "Bearer", "Bearer wrong-token"],
)
async def test_service_authentication_rejects_missing_or_invalid_credentials(
    authorization: str | None,
) -> None:
    app = create_app(settings=_settings())

    @app.get("/protected", dependencies=[Depends(require_service_token)])
    async def protected() -> dict[str, bool]:
        return {"accepted": True}

    headers = {"Authorization": authorization} if authorization is not None else {}
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/protected", headers=headers)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.asyncio
async def test_service_authentication_fails_closed_without_configured_tokens() -> None:
    settings = _settings()
    app = create_app(
        settings=ApiSettings(
            environment=settings.environment,
            policy_version=settings.policy_version,
            bearer_tokens=(),
            max_body_bytes=settings.max_body_bytes,
            idempotency_key_max_bytes=settings.idempotency_key_max_bytes,
            sse_heartbeat_seconds=settings.sse_heartbeat_seconds,
            sse_buffer_size=settings.sse_buffer_size,
        )
    )

    @app.get("/protected", dependencies=[Depends(require_service_token)])
    async def protected() -> dict[str, bool]:
        return {"accepted": True}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/protected", headers={"Authorization": "Bearer anything"})

    assert response.status_code == 503


@pytest.mark.asyncio
async def test_service_authentication_accepts_configured_token() -> None:
    app = create_app(settings=_settings())

    @app.get("/protected", dependencies=[Depends(require_service_token)])
    async def protected() -> dict[str, bool]:
        return {"accepted": True}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/protected", headers={"Authorization": "Bearer test-token"})

    assert response.status_code == 200
    assert response.json() == {"accepted": True}


@pytest.mark.asyncio
@pytest.mark.parametrize("key", [None, "contains spaces", "!invalid", "x" * 129])
async def test_write_dependency_rejects_missing_or_invalid_idempotency_key(
    key: str | None,
) -> None:
    app = create_app(settings=_settings())

    @app.post("/write")
    async def write(idempotency_key: str = Depends(require_idempotency_key)) -> dict[str, str]:
        return {"idempotency_key": idempotency_key}

    headers = {"Idempotency-Key": key} if key is not None else {}
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/write", headers=headers)

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_write_dependency_accepts_safe_idempotency_key() -> None:
    app = create_app(settings=_settings())

    @app.post("/write")
    async def write(idempotency_key: str = Depends(require_idempotency_key)) -> dict[str, str]:
        return {"idempotency_key": idempotency_key}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/write", headers={"Idempotency-Key": "request:123-v1"})

    assert response.status_code == 200
    assert response.json() == {"idempotency_key": "request:123-v1"}
