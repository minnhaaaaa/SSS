from __future__ import annotations

import httpx
import pytest
from sss_api.config import ApiSettings
from sss_api.demo_composition import build_demo_services
from sss_api.main import create_app


@pytest.mark.asyncio
async def test_observation_api_assigns_kind_and_rejects_unknown_telemetry() -> None:
    calls: list[tuple[str, object, str]] = []

    class Repository:
        def record(self, kind: str, payload: object, key: str) -> str:
            calls.append((kind, payload, key))
            return "observation-1"

    settings = ApiSettings(
        environment="test",
        policy_version="sss-hackathon-v3",
        bearer_tokens=("collector-token",),
        max_body_bytes=1_048_576,
        idempotency_key_max_bytes=128,
        sse_heartbeat_seconds=15,
        sse_buffer_size=10,
    )
    services = build_demo_services(settings)
    app = create_app(
        settings=settings,
        service_factory=lambda _: services.__class__(
            **{
                field: getattr(services, field)
                for field in services.__dataclass_fields__
                if field != "observation_repository"
            },
            observation_repository=Repository(),
        ),
    )
    body = {
        "observation_id": "observation-1",
        "package": {
            "ecosystem": "npm",
            "registry_origin": "https://registry.npmjs.org",
            "canonical_name": "novel-agent-tool",
        },
        "client_pseudonym": "client-0001",
        "agent_family": "codex",
        "requested_source": "registry",
        "observed_at": "2026-09-13T10:00:00Z",
    }
    headers = {
        "Authorization": "Bearer collector-token",
        "Idempotency-Key": "observation-key",
    }
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        accepted = await client.post("/v1/observations/client", json=body, headers=headers)
        rejected = await client.post(
            "/v1/observations/client",
            json={**body, "raw_command": "npm install secret"},
            headers=headers,
        )

    assert accepted.status_code == 202
    assert accepted.json() == {"observation_id": "observation-1", "accepted": True}
    assert rejected.status_code == 422
    assert calls[0][0] == "client"
    assert calls[0][2] == "observation-key"
