from __future__ import annotations

from sss_api.config import ApiSettings
from sss_api.services.readiness import ReadinessService
from sss_core.policy.engine import POLICY_VERSION
from sss_core.repositories.exasol import SchemaReadiness


def _settings(*, required: bool = False, policy: str = POLICY_VERSION) -> ApiSettings:
    return ApiSettings(
        environment="test",
        policy_version=policy,
        bearer_tokens=("test",),
        max_body_bytes=128,
        idempotency_key_max_bytes=128,
        sse_heartbeat_seconds=1,
        sse_buffer_size=8,
        exasol_required=required,
    )


class ReadyChecker:
    def check(self, connection: object) -> SchemaReadiness:
        assert connection is not None
        return SchemaReadiness("001", "001", (), (), (), ())


def test_readiness_accepts_matching_policy_without_optional_exasol() -> None:
    result = ReadinessService(
        settings=_settings(), connection=None, schema_checker=ReadyChecker()
    ).check()

    assert result.ready
    assert result.exasol["status"] == "not_required"


def test_readiness_fails_closed_when_required_exasol_is_unavailable() -> None:
    result = ReadinessService(
        settings=_settings(required=True), connection=None, schema_checker=ReadyChecker()
    ).check()

    assert not result.ready
    assert result.exasol["status"] == "unavailable"


def test_readiness_detects_policy_version_drift() -> None:
    result = ReadinessService(
        settings=_settings(policy="unexpected"), connection=None, schema_checker=ReadyChecker()
    ).check()

    assert not result.ready
    assert result.policy["engine_version"] == POLICY_VERSION
