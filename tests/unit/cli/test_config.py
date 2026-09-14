from __future__ import annotations

import os
from pathlib import Path

import pytest
from sss_cli.config import CliConfigurationError, CliSettings, OperatorSettings


def test_cli_settings_require_absolute_real_executables() -> None:
    values = {
        "SSS_API_URL": "https://api.example.test",
        "SSS_GATEWAY_URL": "https://gateway.example.test",
        "SSS_PROTECTED_API_URL": "http://api:8000",
        "SSS_PROTECTED_GATEWAY_URL": "http://gateway:8080",
        "SSS_REAL_EXECUTABLES_JSON": '{"pnpm":"relative/pnpm"}',
    }

    with pytest.raises(CliConfigurationError, match="must be absolute"):
        CliSettings.from_env(values)


def test_cli_settings_reject_credentials_in_service_url() -> None:
    values = {
        "SSS_API_URL": "https://user:password@api.example.test",
        "SSS_GATEWAY_URL": "https://gateway.example.test",
        "SSS_PROTECTED_API_URL": "http://api:8000",
        "SSS_PROTECTED_GATEWAY_URL": "http://gateway:8080",
    }

    with pytest.raises(CliConfigurationError, match="cannot contain credentials"):
        CliSettings.from_env(values)


def test_operator_settings_do_not_require_package_manager_configuration() -> None:
    settings = OperatorSettings.from_env(
        {
            "SSS_API_URL": "http://127.0.0.1:8000",
            "SSS_API_TOKEN": "operator-token",
            "SSS_GATEWAY_URL": "",
        }
    )

    assert settings.api_url == "http://127.0.0.1:8000"
    assert settings.api_token == "operator-token"  # noqa: S105 - explicit test credential.


def test_cli_reads_agent_token_from_restricted_secret_file(tmp_path: Path) -> None:
    token_file = tmp_path / "agent-token"
    token_file.write_text("session-token\n", encoding="utf-8")
    os.chmod(token_file, 0o400)

    settings = CliSettings.from_env(
        {
            "SSS_API_URL": "http://api:8000",
            "SSS_GATEWAY_URL": "http://gateway:8080",
            "SSS_API_TOKEN_FILE": str(token_file),
        }
    )

    assert settings.api_token == "session-token"  # noqa: S105
