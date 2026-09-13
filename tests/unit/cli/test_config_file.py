from __future__ import annotations

import json

import pytest
from sss_cli.config import CliConfigurationError
from sss_cli.config_file import StoredCliConfig, load_config, write_config


def _token(tmp_path):  # type: ignore[no-untyped-def]
    path = tmp_path / "guard.token"
    path.write_text("raw-secret-token\n", encoding="utf-8")
    path.chmod(0o600)
    return path


def test_config_is_atomic_mode_0600_and_never_contains_token(tmp_path) -> None:  # type: ignore[no-untyped-def]
    token = _token(tmp_path)
    destination = tmp_path / "config" / "config.json"
    config = StoredCliConfig("https://sss.example.test", token, "acme", "project-1")

    write_config(config, destination)

    assert destination.stat().st_mode & 0o777 == 0o600
    assert destination.parent.stat().st_mode & 0o777 == 0o700
    assert "raw-secret-token" not in destination.read_text(encoding="utf-8")
    assert load_config(destination).read_token() == "raw-secret-token"


@pytest.mark.parametrize(
    "server",
    ["http://example.test", "ftp://example.test", "https://user:pass@example.test"],
)
def test_config_rejects_unsafe_servers(tmp_path, server: str) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(CliConfigurationError):
        StoredCliConfig(server, _token(tmp_path), "acme", "project-1")


def test_config_allows_explicit_loopback_http(tmp_path) -> None:  # type: ignore[no-untyped-def]
    config = StoredCliConfig(
        "http://127.0.0.1:8000", _token(tmp_path), "acme", "project-1"
    )
    assert config.server == "http://127.0.0.1:8000"


def test_invalid_config_error_never_contains_token_contents(tmp_path) -> None:  # type: ignore[no-untyped-def]
    destination = tmp_path / "config.json"
    destination.write_text(json.dumps({"token": "raw-secret-token"}), encoding="utf-8")
    destination.chmod(0o600)
    with pytest.raises(CliConfigurationError) as raised:
        load_config(destination)
    assert "raw-secret-token" not in str(raised.value)
