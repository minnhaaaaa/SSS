from __future__ import annotations

import pytest
from sss_api.config import ApiSettings, ConfigurationError


def test_api_settings_read_runtime_values() -> None:
    settings = ApiSettings.from_env(
        {
            "SSS_ENV": "test",
            "SSS_POLICY_VERSION": "policy-under-test",
            "SSS_API_BEARER_TOKENS": "first, second ",
            "SSS_API_MAX_BODY_BYTES": "256",
            "SSS_IDEMPOTENCY_KEY_MAX_BYTES": "64",
            "SSS_SSE_HEARTBEAT_SECONDS": "2",
            "SSS_SSE_BUFFER_SIZE": "4",
            "SSS_EXASOL_REQUIRED": "true",
        }
    )

    assert settings.environment == "test"
    assert settings.bearer_tokens == ("first", "second")
    assert settings.max_body_bytes == 256
    assert settings.idempotency_key_max_bytes == 64
    assert settings.sse_heartbeat_seconds == 2
    assert settings.sse_buffer_size == 4
    assert settings.exasol_required is True


def test_api_settings_reject_non_positive_limits() -> None:
    with pytest.raises(ConfigurationError, match="must be positive"):
        ApiSettings.from_env({"SSS_API_MAX_BODY_BYTES": "0"})


def test_api_settings_reject_ambiguous_exasol_requirement() -> None:
    with pytest.raises(ConfigurationError, match="must be true or false"):
        ApiSettings.from_env({"SSS_EXASOL_REQUIRED": "sometimes"})
