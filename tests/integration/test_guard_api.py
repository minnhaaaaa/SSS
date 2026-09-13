from __future__ import annotations

import httpx
from sss_api.config import ApiSettings
from sss_api.main import create_app


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


def _payload() -> dict[str, object]:
    return {
        "request_id": "req-demo-001",
        "project_id": "project-demo",
        "agent_family": "codex",
        "package": {
            "ecosystem": "npm",
            "registry_origin": "https://npm.demo.sss.test",
            "canonical_name": "@sss-demo/reserved-synthetic",
        },
        "version_spec": "1.0.0",
        "direct_url": None,
        "artifact_sha256": "b" * 64,
        "is_direct": True,
    }


async def test_check_requires_authentication_and_idempotency() -> None:
    app = create_app(settings=_settings())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        unauthenticated = await client.post("/v1/check", json=_payload())
        missing_key = await client.post(
            "/v1/check",
            json=_payload(),
            headers={"Authorization": "Bearer test-token"},
        )

    assert unauthenticated.status_code == 401
    assert missing_key.status_code == 400


async def test_check_returns_frozen_block_and_pending_intervention_once() -> None:
    app = create_app(settings=_settings())
    transport = httpx.ASGITransport(app=app)
    headers = {
        "Authorization": "Bearer test-token",
        "Idempotency-Key": "demo-check-1",
    }
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post("/v1/check", json=_payload(), headers=headers)
        second = await client.post("/v1/check", json=_payload(), headers=headers)
        interventions = await client.get(
            "/v1/interventions", headers={"Authorization": "Bearer test-token"}
        )

    assert first.status_code == 200
    assert second.json() == first.json()
    body = first.json()
    assert body["decision"] == "block"
    assert body["reason_codes"] == [
        "REGISTERED_AFTER_HALLUCINATION",
        "HIGH_GLOBAL_RECURRENCE",
    ]
    assert body["scores"] == {
        "absence_confidence": 100,
        "target_attractiveness": 95,
        "package_policy_risk": 75,
    }
    assert body["child_process_allowed"] is False
    assert interventions.status_code == 200
    assert len(interventions.json()["items"]) == 1


async def test_check_rejects_unknown_fields() -> None:
    app = create_app(settings=_settings())
    transport = httpx.ASGITransport(app=app)
    payload = {**_payload(), "unexpected": "value"}
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/check",
            json=payload,
            headers={
                "Authorization": "Bearer test-token",
                "Idempotency-Key": "demo-check-extra",
            },
        )

    assert response.status_code == 422
