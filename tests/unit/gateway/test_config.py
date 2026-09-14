from __future__ import annotations

import pytest
from sss_gateway.config import GatewayConfigurationError, GatewaySettings


def test_gateway_settings_are_loaded_from_environment() -> None:
    settings = GatewaySettings.from_env(
        {
            "SSS_GATEWAY_UPSTREAMS_JSON": (
                '{"pypi":"https://pypi.example.test","npm":"https://npm.example.test"}'
            ),
            "SSS_GATEWAY_MAX_ARTIFACT_BYTES": "100",
            "SSS_GATEWAY_MAX_EXPANDED_BYTES": "200",
            "SSS_GATEWAY_MAX_ARCHIVE_ENTRIES": "3",
            "SSS_GATEWAY_MAX_FILE_BYTES": "50",
            "SSS_GATEWAY_MAX_COMPRESSION_RATIO": "10",
            "SSS_GATEWAY_CONNECT_TIMEOUT_SECONDS": "1.5",
            "SSS_GATEWAY_READ_TIMEOUT_SECONDS": "2.5",
        }
    )

    assert settings.upstreams["pypi"] == "https://pypi.example.test"
    assert settings.archive_limits.max_expanded_bytes == 200
    assert settings.archive_limits.max_entries == 3
    assert settings.connect_timeout_seconds == 1.5
    assert settings.read_timeout_seconds == 2.5


def test_gateway_settings_require_an_allowlist() -> None:
    with pytest.raises(GatewayConfigurationError, match="required"):
        GatewaySettings.from_env({})


def test_gateway_settings_reject_non_positive_limits() -> None:
    with pytest.raises(GatewayConfigurationError, match="must be positive"):
        GatewaySettings.from_env(
            {
                "SSS_GATEWAY_UPSTREAMS_JSON": '{"pypi":"https://pypi.example.test"}',
                "SSS_GATEWAY_MAX_ARTIFACT_BYTES": "0",
            }
        )
