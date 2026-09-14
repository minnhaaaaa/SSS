"""Fail-closed Compose configuration for a protected agent session."""

from __future__ import annotations

import re
from collections.abc import Mapping

from sss_cli.config import CliConfigurationError, CliSettings
from sss_cli.environment import build_minimal_environment

_DIGEST_PINNED_IMAGE = re.compile(r"^\S+@sha256:[0-9a-fA-F]{64}$")


def validate_digest_pinned_image(image: str) -> str:
    if not _DIGEST_PINNED_IMAGE.fullmatch(image):
        raise CliConfigurationError(
            "SSS_AGENT_IMAGE must use an immutable @sha256 digest reference"
        )
    return image


def build_protected_compose_environment(
    settings: CliSettings,
    source: Mapping[str, str],
) -> dict[str, str]:
    required = {
        "SSS_API_URL": settings.protected_api_url,
        "SSS_GATEWAY_URL": settings.protected_gateway_url,
        "SSS_AGENT_IMAGE": settings.agent_image,
        "SSS_PROTECTED_NETWORK": settings.protected_network,
        "SSS_PROJECT_PATH": str(settings.project_path.resolve()) if settings.project_path else None,
        "SSS_GUARD_SESSION_TOKEN": settings.guard_session_token,
        "SSS_ARTIFACT_SHA256": source.get("SSS_ARTIFACT_SHA256"),
        "SSS_PROJECT_ID": settings.project_id,
        "SSS_AGENT_FAMILY": settings.agent_family,
    }
    agent_image = settings.agent_image
    if agent_image is None:
        raise CliConfigurationError("SSS_AGENT_IMAGE is required")
    validate_digest_pinned_image(agent_image)
    missing = sorted(key for key, value in required.items() if not value)
    if missing:
        raise CliConfigurationError(
            f"protected session configuration is missing: {', '.join(missing)}"
        )
    if settings.project_path is None or not settings.project_path.is_dir():
        raise CliConfigurationError("SSS_PROJECT_PATH must be an existing directory")
    artifact = required["SSS_ARTIFACT_SHA256"]
    if artifact is None or not re.fullmatch(r"[a-f0-9]{64}", artifact):
        raise CliConfigurationError("SSS_ARTIFACT_SHA256 must be a lowercase SHA-256")

    return build_minimal_environment(
        source,
        allowed_keys=settings.allowed_environment_keys,
        overrides={
            **{key: value for key, value in required.items() if value is not None},
        },
    )
