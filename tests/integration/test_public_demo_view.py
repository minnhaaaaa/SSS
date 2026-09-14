from __future__ import annotations

import httpx
from sss_api.config import ApiSettings
from sss_api.main import create_app
from sss_api.services.demo import DemoController


class NoopRepository:
    def reset(self) -> None:
        return None

    def replay(self) -> None:
        return None


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


async def test_public_demo_view_is_redacted_read_only_and_matches_frozen_fixture() -> None:
    controller = DemoController(repository=NoopRepository())
    controller.replay()
    controller.register()
    controller.record_unprotected(canary_before=0, canary_after=1)
    controller.record_protected(
        exit_code=23,
        child_process_started=False,
        canary_after=1,
    )
    app = create_app(settings=_settings(), demo_controller=controller)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        status = await client.get("/v1/public/demo")
        packages = await client.get("/v1/public/packages")
        decisions = await client.get("/v1/public/decisions")
        mutation = await client.post("/v1/public/demo/replay-evidence")

    assert status.status_code == 200
    assert status.json() == {
        "state": "blocked",
        "completed_steps": [
            "replay-evidence",
            "register-target",
            "run-unprotected",
            "run-protected",
        ],
        "available_actions": [],
        "target_package": "@sss-demo/reserved-synthetic",
        "unprotected_canary_count": 1,
        "protected_canary_count": 0,
        "package_manager_started": False,
        "message": "Agent install blocked before pnpm; review it with `sss intervene --watch`.",
        "scores": {
            "absence_confidence": 100,
            "target_attractiveness": 95,
            "package_policy_risk": 75,
        },
        "policy_version": "sss-hackathon-v3",
        "registration_age_minutes": 43,
    }
    assert packages.json()[0]["name"] == "@sss-demo/reserved-synthetic"
    assert packages.json()[0]["policy_risk"] == 75
    assert decisions.json() == []
    assert mutation.status_code == 404
