from __future__ import annotations

from pathlib import Path

import pytest
from sss_cli.config import CliConfigurationError, CliSettings
from sss_cli.protected_config import (
    build_protected_compose_environment,
    validate_digest_pinned_image,
)

_PINNED_AGENT_IMAGE = f"agent@sha256:{'a' * 64}"


def _settings(base_project_path: Path, **overrides: object) -> CliSettings:
    values: dict[str, object] = {
        "api_url": "https://api.example.test",
        "gateway_url": "https://gateway.example.test",
        "protected_api_url": "http://api:8000",
        "protected_gateway_url": "http://gateway:8080",
        "api_token": None,
        "real_executables": {},
        "allowed_environment_keys": frozenset({"PATH", "SYSTEMROOT"}),
        "docker_executable": "docker",
        "protected_compose_file": Path("compose.protected.yaml"),
        "protected_service": "protected-agent",
        "agent_image": _PINNED_AGENT_IMAGE,
        "protected_network": "sss-protected",
        "project_path": base_project_path,
        "guard_session_token": "short-lived-token",
    }
    values.update(overrides)
    return CliSettings(**values)  # type: ignore[arg-type]


def test_protected_compose_environment_contains_only_runtime_session_values(
    tmp_path: Path,
) -> None:
    environment = build_protected_compose_environment(
        _settings(tmp_path),
        {
            "PATH": "/safe/bin",
            "SYSTEMROOT": "C:\\Windows",
            "SSS_APPROVAL_SIGNING_KEY": "must-not-leak",
            "SSS_API_BEARER_TOKENS": "must-not-leak",
            "SSS_EXASOL_PASSWORD": "must-not-leak",
        },
    )

    assert environment == {
        "PATH": "/safe/bin",
        "SYSTEMROOT": "C:\\Windows",
        "SSS_API_URL": "http://api:8000",
        "SSS_GATEWAY_URL": "http://gateway:8080",
        "SSS_AGENT_IMAGE": _PINNED_AGENT_IMAGE,
        "SSS_PROTECTED_NETWORK": "sss-protected",
        "SSS_PROJECT_PATH": str(tmp_path.resolve()),
        "SSS_GUARD_SESSION_TOKEN": "short-lived-token",
    }


@pytest.mark.parametrize(
    ("field", "environment_name"),
    [
        ("agent_image", "SSS_AGENT_IMAGE"),
        ("protected_network", "SSS_PROTECTED_NETWORK"),
        ("project_path", "SSS_PROJECT_PATH"),
        ("guard_session_token", "SSS_GUARD_SESSION_TOKEN"),
    ],
)
def test_protected_compose_environment_requires_every_session_value(
    tmp_path: Path,
    field: str,
    environment_name: str,
) -> None:
    with pytest.raises(CliConfigurationError, match=environment_name):
        build_protected_compose_environment(_settings(tmp_path, **{field: None}), {})


@pytest.mark.parametrize(
    "image",
    [
        "agent:latest",
        "agent@sha256:short",
        f"agent@sha512:{'a' * 64}",
        f"agent name@sha256:{'a' * 64}",
    ],
)
def test_protected_compose_environment_rejects_floating_or_invalid_images(
    tmp_path: Path,
    image: str,
) -> None:
    with pytest.raises(CliConfigurationError, match="immutable @sha256"):
        build_protected_compose_environment(_settings(tmp_path, agent_image=image), {})


def test_digest_pinned_image_accepts_registry_and_port() -> None:
    image = f"registry.example.test:5000/team/agent@sha256:{'f' * 64}"

    assert validate_digest_pinned_image(image) == image
