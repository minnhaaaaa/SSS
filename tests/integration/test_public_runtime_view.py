from __future__ import annotations

import httpx
from sss_api.config import ApiSettings
from sss_api.main import create_app


def _settings() -> ApiSettings:
    return ApiSettings(
        environment="test",
        policy_version="sss-hackathon-v3",
        bearer_tokens=("private-token",),
        max_body_bytes=4096,
        idempotency_key_max_bytes=128,
        sse_heartbeat_seconds=1,
        sse_buffer_size=8,
    )


async def test_public_views_reflect_only_received_runtime_activity() -> None:
    app = create_app(settings=_settings())
    transport = httpx.ASGITransport(app=app)
    auth = {"Authorization": "Bearer private-token"}
    check_headers = {**auth, "Idempotency-Key": "runtime-check-1"}
    observation_headers = {**auth, "Idempotency-Key": "runtime-observation-1"}
    package = {
        "ecosystem": "npm",
        "registry_origin": "https://registry.npmjs.org",
        "canonical_name": "runtime-package",
    }
    check_payload = {
        "request_id": "runtime-request-1",
        "project_id": "runtime-project",
        "agent_family": "test-agent",
        "package": package,
        "version_spec": "1.0.0",
        "direct_url": None,
        "artifact_sha256": None,
        "is_direct": False,
    }
    observation_payload = {
        "observation_id": "runtime-observation-1",
        "package": package,
        "observed_at": "2026-09-13T10:00:00Z",
        "explicit_install_context": False,
        "evidence_label": "Observed during a runtime model probe",
        "provenance": "model_probe",
        "source_id": "runtime-source-1",
        "model_configuration_id": "runtime-model-config-1",
    }

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        empty_packages = await client.get("/v1/public/packages")
        check = await client.post("/v1/check", json=check_payload, headers=check_headers)
        observed = await client.post(
            "/v1/observations/model",
            json=observation_payload,
            headers=observation_headers,
        )
        overview = await client.get("/v1/public/overview")
        packages = await client.get("/v1/public/packages")
        decisions = await client.get("/v1/public/decisions")
        coverage = await client.get("/v1/public/coverage")
        removed_demo_route = await client.get("/v1/public/demo")

    assert empty_packages.json() == []
    assert check.status_code == 200
    assert observed.status_code == 201
    assert [item["name"] for item in packages.json()] == ["runtime-package"]
    assert overview.json()["radar_nodes"] == packages.json()
    assert overview.json()["guard_status"] == "degraded"
    assert overview.json()["active_threats"] == 0
    assert overview.json()["verified_recommendations"] == 1
    assert decisions.json()[0]["id"] == check.json()["decision_id"]
    assert decisions.json()[0]["package_name"] == "runtime-package"
    assert decisions.json()[0]["package_manager_started"] is None
    assert coverage.json()["verified_recommendations"] == 1
    assert coverage.json()["model_configurations"] == 1
    assert removed_demo_route.status_code == 404
