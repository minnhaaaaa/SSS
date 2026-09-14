from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from sss_canary.config import CanarySettings
from sss_canary.main import create_app


@pytest.mark.asyncio
async def test_canary_records_and_resets_authenticated_events(tmp_path: Path) -> None:
    settings = CanarySettings(
        database_path=tmp_path / "events.db",
        token="test-token",
        marker="test-marker",
    )
    transport = httpx.ASGITransport(app=create_app(settings=settings))
    headers = {"Authorization": "Bearer test-token"}

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/v1/count", headers=headers)).json() == {"count": 0}
        created = await client.post("/v1/events", headers=headers, json={"marker": "test-marker"})
        assert created.status_code == 201
        assert (await client.get("/v1/count", headers=headers)).json() == {"count": 1}
        assert (await client.post("/v1/reset", headers=headers)).json() == {"count": 0}


@pytest.mark.asyncio
async def test_canary_rejects_wrong_marker_without_recording(tmp_path: Path) -> None:
    settings = CanarySettings(
        database_path=tmp_path / "events.db",
        token="test-token",
        marker="expected-marker",
    )
    transport = httpx.ASGITransport(app=create_app(settings=settings))
    headers = {"Authorization": "Bearer test-token"}

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/events", headers=headers, json={"marker": "wrong-marker"})

        assert response.status_code == 422
        assert (await client.get("/v1/count", headers=headers)).json() == {"count": 0}


@pytest.mark.asyncio
async def test_canary_rejects_unauthenticated_requests(tmp_path: Path) -> None:
    settings = CanarySettings(
        database_path=tmp_path / "events.db",
        token="test-token",
        marker="test-marker",
    )
    transport = httpx.ASGITransport(app=create_app(settings=settings))

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/count")

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.asyncio
async def test_canary_rejects_unknown_payload_fields(tmp_path: Path) -> None:
    settings = CanarySettings(
        database_path=tmp_path / "events.db",
        token="test-token",
        marker="test-marker",
    )
    transport = httpx.ASGITransport(app=create_app(settings=settings))

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/events",
            headers={"Authorization": "Bearer test-token"},
            json={"marker": "test-marker", "unexpected": "value"},
        )

    assert response.status_code == 422
