"""Credential-free environment for an allowed real package-manager process."""

from __future__ import annotations

from collections.abc import Mapping

from sss_cli.config import CliSettings
from sss_cli.environment import FORBIDDEN_EXACT_KEYS, build_minimal_environment

_MANAGER_FORBIDDEN_KEYS = FORBIDDEN_EXACT_KEYS | frozenset(
    {
        "SSS_API_TOKEN",
        "SSS_GUARD_SESSION_TOKEN",
        "SSS_APPROVAL_TOKEN",
        "SSS_APPROVAL_NONCE",
    }
)


def build_manager_environment(
    settings: CliSettings,
    source: Mapping[str, str],
) -> dict[str, str]:
    gateway = settings.gateway_url
    return build_minimal_environment(
        source,
        allowed_keys=settings.allowed_environment_keys,
        forbidden_keys=_MANAGER_FORBIDDEN_KEYS,
        overrides={
            "NPM_CONFIG_REGISTRY": f"{gateway}/v1/registry/npm",
            "YARN_NPM_REGISTRY_SERVER": f"{gateway}/v1/registry/npm",
            "PIP_INDEX_URL": f"{gateway}/v1/registry/pypi/simple",
            "UV_INDEX_URL": f"{gateway}/v1/registry/pypi/simple",
        },
    )
