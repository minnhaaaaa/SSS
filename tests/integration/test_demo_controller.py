from __future__ import annotations

import httpx
import pytest
from sss_api.config import ApiSettings
from sss_api.main import create_app
from sss_api.services.demo import DemoController, DemoState


class RecordingDemoRepository:
    def __init__(self) -> None:
        self.reset_calls = 0
        self.replay_calls = 0

    def reset(self) -> None:
        self.reset_calls += 1

    def replay(self) -> None:
        self.replay_calls += 1


def test_demo_controller_is_idempotent_and_requires_exact_sequence() -> None:
    repository = RecordingDemoRepository()
    controller = DemoController(repository=repository)

    assert controller.reset().state is DemoState.READY
    assert controller.reset().state is DemoState.READY
    assert repository.reset_calls == 2
    with pytest.raises(ValueError, match="replay evidence"):
        controller.register()
    assert controller.replay().state is DemoState.REPLAYED
    assert controller.replay().state is DemoState.REPLAYED
    assert repository.replay_calls == 1
    assert controller.register().state is DemoState.REGISTERED
    assert (
        controller.record_unprotected(canary_before=0, canary_after=1).state
        is DemoState.UNPROTECTED
    )
    status = controller.record_protected(
        exit_code=23,
        child_process_started=False,
        canary_after=1,
    )
    assert status.state is DemoState.PROTECTED_BLOCKED
    assert status.canary_count == 1
    assert status.protected_child_started is False


def _settings() -> ApiSettings:
    return ApiSettings(
        environment="test",
        policy_version="sss-hackathon-v3",
        bearer_tokens=("demo-token",),
        max_body_bytes=4096,
        idempotency_key_max_bytes=128,
        sse_heartbeat_seconds=1,
        sse_buffer_size=8,
    )


async def test_demo_routes_report_and_advance_controlled_state() -> None:
    controller = DemoController(repository=RecordingDemoRepository())
    app = create_app(settings=_settings(), demo_controller=controller)
    transport = httpx.ASGITransport(app=app)
    auth = {"Authorization": "Bearer demo-token"}
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        unauthorized = await client.get("/v1/demo/status")
        reset = await client.post(
            "/v1/demo/reset",
            headers={**auth, "Idempotency-Key": "demo-reset"},
        )
        replay = await client.post(
            "/v1/demo/replay",
            headers={**auth, "Idempotency-Key": "demo-replay"},
        )
        registered = await client.post(
            "/v1/demo/register",
            headers={**auth, "Idempotency-Key": "demo-register"},
        )
        unprotected = await client.post(
            "/v1/demo/unprotected",
            json={"canary_before": 0, "canary_after": 1},
            headers={**auth, "Idempotency-Key": "demo-unprotected"},
        )
        protected = await client.post(
            "/v1/demo/protected",
            json={"exit_code": 23, "child_process_started": False, "canary_after": 1},
            headers={**auth, "Idempotency-Key": "demo-protected"},
        )

    assert unauthorized.status_code == 401
    assert [
        reset.json()["state"],
        replay.json()["state"],
        registered.json()["state"],
        unprotected.json()["state"],
        protected.json()["state"],
    ] == ["ready", "replayed", "registered", "unprotected", "protected_blocked"]
    assert protected.json()["protected_child_started"] is False
