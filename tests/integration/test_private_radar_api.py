from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from sss_api.config import ApiSettings
from sss_api.demo_composition import build_demo_services
from sss_api.main import create_app


@pytest.mark.asyncio
async def test_private_radar_requires_scope_and_returns_opaque_cursor() -> None:
    class Repository:
        def list_private_page(self, *, limit: int, cursor):  # type: ignore[no-untyped-def]
            assert limit == 1
            assert cursor is None
            return [
                {
                    "ecosystem": "npm",
                    "registry_origin": "https://registry.npmjs.org",
                    "canonical_name": "novel-agent-tool",
                    "status": "registered_after_absence",
                    "first_absence_at": "2026-09-12T10:00:00Z",
                    "first_registration_at": "2026-09-13T10:00:00Z",
                    "synthetic": False,
                    "verified_model_recommendations": 20,
                    "model_configurations": 2,
                    "protected_agent_attempts": 6,
                    "public_failed_references": 4,
                    "observation_days": 3,
                    "has_explicit_context": True,
                }
            ], (datetime(2026, 9, 13, 10, tzinfo=UTC), "novel-agent-tool")

    settings = ApiSettings(
        environment="test",
        policy_version="sss-hackathon-v3",
        bearer_tokens=("radar-token",),
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
                if field != "radar_repository"
            },
            radar_repository=Repository(),
        ),
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        missing = await client.get("/v1/radar?limit=1")
        valid = await client.get(
            "/v1/radar?limit=1", headers={"Authorization": "Bearer radar-token"}
        )

    assert missing.status_code == 401
    assert valid.status_code == 200
    assert valid.json()["items"][0]["canonical_name"] == "novel-agent-tool"
    assert valid.json()["next_cursor"]
