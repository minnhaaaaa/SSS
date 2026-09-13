from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import httpx
import pytest
from sss_api.config import ApiSettings
from sss_api.demo_composition import build_demo_services
from sss_api.main import create_app

NOW = datetime(2026, 9, 14, 10, tzinfo=UTC)


class UiRepository:
    def data_as_of(self) -> datetime:
        return NOW

    def list_private_page(self, *, limit: int, cursor=None):  # type: ignore[no-untyped-def]
        del limit, cursor
        return [], None

    def list_ui_packages(self, *, limit: int):  # type: ignore[no-untyped-def]
        del limit
        return [
            {
                "id": "pkg-novel",
                "name": "novel-agent-tool",
                "ecosystem": "npm",
                "registry_origin": "https://registry.npmjs.org",
                "state": "blocked",
                "attractiveness": 62,
                "policy_risk": 75,
                "last_seen": NOW.isoformat(),
            },
            {
                "id": "pkg-safe",
                "name": "safe-lib",
                "ecosystem": "pypi",
                "registry_origin": "https://pypi.org/simple",
                "state": "registered",
                "attractiveness": 0,
                "policy_risk": 0,
                "last_seen": NOW.isoformat(),
            },
        ]

    def get_ui_package(self, name: str):  # type: ignore[no-untyped-def]
        package = next(item for item in self.list_ui_packages(limit=200) if item["name"] == name)
        return {**package, "absence_confidence": 100, "lifecycle": ["absence verified"]}

    def list_ui_evidence(self, name: str):  # type: ignore[no-untyped-def]
        return [
            {
                "id": f"evidence-{name}",
                "type": "absent",
                "label": "npm absent",
                "provenance": "registry",
                "occurred_at": NOW.isoformat(),
            }
        ]

    def list_ui_decisions(self, *, limit: int):  # type: ignore[no-untyped-def]
        del limit
        return [
            {
                "id": "decision-1",
                "package_name": "novel-agent-tool",
                "ecosystem": "npm",
                "result": "block",
                "policy": "sss-hackathon-v3",
                "occurred_at": NOW.isoformat(),
                "reason_codes": ["REGISTERED_AFTER_HALLUCINATION"],
                "package_manager_started": False,
                "package_code_executed": False,
            }
        ]

    def coverage(self):  # type: ignore[no-untyped-def]
        return {
            "data_as_of": NOW.isoformat(),
            "registries": [],
            "services": [],
            "protected_agents": 6,
            "observation_days": 3,
            "verified_recommendations": 20,
            "public_failed_references": 4,
            "model_configurations": 2,
        }

    def public_aggregates(self):  # type: ignore[no-untyped-def]
        return {
            "data_as_of": NOW.isoformat(),
            "groups": [
                {
                    "ecosystem": "npm",
                    "status": "registered_after_absence",
                    "package_count": 1,
                    "synthetic_package_count": 0,
                }
            ],
        }


def app_with_private_repository():  # type: ignore[no-untyped-def]
    settings = ApiSettings(
        environment="test",
        policy_version="sss-hackathon-v3",
        bearer_tokens=("radar-token",),
        max_body_bytes=1_048_576,
        idempotency_key_max_bytes=128,
        sse_heartbeat_seconds=1,
        sse_buffer_size=10,
    )
    services = build_demo_services(settings)
    private_services = replace(
        services,
        demo_controller=None,
        demo_fixture=None,
        radar_repository=UiRepository(),
    )
    return create_app(settings=settings, service_factory=lambda _: private_services)


@pytest.mark.asyncio
async def test_private_ui_routes_use_repository_without_demo_fixture() -> None:
    transport = httpx.ASGITransport(app=app_with_private_repository())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        unauthorized = await client.get("/v1/packages")
        response = await client.get(
            "/v1/packages", headers={"Authorization": "Bearer radar-token"}
        )
        old_fixture_route = await client.get("/v1/public/packages")

    assert unauthorized.status_code == 401
    assert response.status_code == 200
    assert [item["name"] for item in response.json()["items"]] == [
        "novel-agent-tool",
        "safe-lib",
    ]
    assert "@sss-demo/reserved-synthetic" not in response.text
    assert response.json()["data_as_of"] == NOW.isoformat()
    assert old_fixture_route.status_code == 404


@pytest.mark.asyncio
async def test_public_aggregates_are_redacted_and_do_not_require_private_token() -> None:
    transport = httpx.ASGITransport(app=app_with_private_repository())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/public/aggregates")

    assert response.status_code == 200
    assert response.json()["groups"][0]["package_count"] == 1
    assert "novel-agent-tool" not in response.text
    assert "safe-lib" not in response.text
