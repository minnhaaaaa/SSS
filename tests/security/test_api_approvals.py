from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta

import httpx
from sss_api.config import ApiSettings
from sss_api.main import create_app
from sss_api.services.approvals import ApprovalService

_KEY = "demo-test-signing-key-with-at-least-32-bytes"


def _settings() -> ApiSettings:
    return ApiSettings(
        environment="test",
        policy_version="sss-hackathon-v3",
        bearer_tokens=("operator-token",),
        max_body_bytes=8192,
        idempotency_key_max_bytes=128,
        sse_heartbeat_seconds=1,
        sse_buffer_size=8,
    )


def _guard_payload() -> dict[str, object]:
    return {
        "request_id": "req-demo-approval",
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


def _claims(*, version: str = "1.0.0") -> dict[str, object]:
    return {
        "package": _guard_payload()["package"],
        "version": version,
        "registry_origin": "https://npm.demo.sss.test",
        "artifact_sha256": "b" * 64,
        "project_id": "project-demo",
        "expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
        "nonce": "nonce-demo-approval",
        "policy_version": "sss-hackathon-v3",
    }


async def _blocked_intervention(client: httpx.AsyncClient) -> str:
    response = await client.post(
        "/v1/check",
        json=_guard_payload(),
        headers={
            "Authorization": "Bearer operator-token",
            "Idempotency-Key": "approval-check",
        },
    )
    assert response.status_code == 200
    return str(response.json()["intervention_id"])


async def test_exact_scope_approval_is_signed_single_use_and_replay_safe() -> None:
    service = ApprovalService(signing_key=_KEY.encode())
    app = create_app(settings=_settings(), approval_service=service)
    transport = httpx.ASGITransport(app=app)
    auth = {"Authorization": "Bearer operator-token"}
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        intervention_id = await _blocked_intervention(client)
        created = await client.post(
            "/v1/approvals",
            json={"intervention_id": intervention_id, "claims": _claims()},
            headers={**auth, "Idempotency-Key": "approval-create"},
        )
        token = created.json()["token"]
        consumed = await client.post(
            "/v1/approvals/consume",
            json={
                "token": token,
                "request_id": "req-demo-approval",
                "expected_nonce": "nonce-demo-approval",
            },
            headers={**auth, "Idempotency-Key": "approval-consume"},
        )
        replay = await client.post(
            "/v1/approvals/consume",
            json={
                "token": token,
                "request_id": "req-demo-approval",
                "expected_nonce": "nonce-demo-approval",
            },
            headers={**auth, "Idempotency-Key": "approval-replay"},
        )

    assert created.status_code == 201
    assert _KEY not in created.text
    assert created.json()["single_use"] is True
    assert consumed.status_code == 200
    assert consumed.json()["consumed"] is True
    assert consumed.json()["remaining_uses"] == 0
    assert replay.status_code == 409


async def test_approval_rejects_scope_widening_and_token_tampering() -> None:
    service = ApprovalService(signing_key=_KEY.encode())
    app = create_app(settings=_settings(), approval_service=service)
    transport = httpx.ASGITransport(app=app)
    auth = {"Authorization": "Bearer operator-token"}
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        intervention_id = await _blocked_intervention(client)
        widened = await client.post(
            "/v1/approvals",
            json={"intervention_id": intervention_id, "claims": _claims(version="2.0.0")},
            headers={**auth, "Idempotency-Key": "approval-widened"},
        )
        created = await client.post(
            "/v1/approvals",
            json={"intervention_id": intervention_id, "claims": _claims()},
            headers={**auth, "Idempotency-Key": "approval-valid"},
        )
        token = created.json()["token"]
        payload, signature = token.split(".")
        decoded = json.loads(base64.urlsafe_b64decode(payload + "=="))
        decoded["version"] = "2.0.0"
        tampered_payload = base64.urlsafe_b64encode(
            json.dumps(decoded, separators=(",", ":"), sort_keys=True).encode()
        ).rstrip(b"=").decode()
        tampered = await client.post(
            "/v1/approvals/consume",
            json={
                "token": f"{tampered_payload}.{signature}",
                "request_id": "req-demo-approval",
                "expected_nonce": "nonce-demo-approval",
            },
            headers={**auth, "Idempotency-Key": "approval-tampered"},
        )

    assert widened.status_code == 409
    assert tampered.status_code == 403
