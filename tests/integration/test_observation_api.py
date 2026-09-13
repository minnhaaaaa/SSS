from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from sss_api.config import ApiSettings
from sss_api.main import create_app

ROOT = Path(__file__).parents[2]


def _settings() -> ApiSettings:
    return ApiSettings(
        environment="test",
        policy_version="sss-hackathon-v3",
        bearer_tokens=("test-token",),
        max_body_bytes=4096,
        idempotency_key_max_bytes=128,
        sse_heartbeat_seconds=1,
        sse_buffer_size=8,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kind", "fixture_name"),
    [
        ("model", "observation-model.json"),
        ("public", "observation-public.json"),
        ("client", "observation-client.json"),
    ],
)
async def test_observation_contracts_are_authenticated_and_idempotent(
    kind: str, fixture_name: str
) -> None:
    payload = json.loads(
        (ROOT / "docs/contracts/examples" / fixture_name).read_text(encoding="utf-8")
    )
    transport = httpx.ASGITransport(app=create_app(settings=_settings()))
    headers = {
        "Authorization": "Bearer test-token",
        "Idempotency-Key": f"observation:{kind}:1",
    }
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post(f"/v1/observations/{kind}", json=payload, headers=headers)
        second = await client.post(f"/v1/observations/{kind}", json=payload, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json() == second.json()


@pytest.mark.asyncio
async def test_observation_rejects_missing_authentication() -> None:
    payload = json.loads(
        (ROOT / "docs/contracts/examples/observation-model.json").read_text(encoding="utf-8")
    )
    transport = httpx.ASGITransport(app=create_app(settings=_settings()))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/observations/model",
            json=payload,
            headers={"Idempotency-Key": "observation:model:1"},
        )

    assert response.status_code == 401
