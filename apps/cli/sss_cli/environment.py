"""Construction of minimal child environments without administrative secrets."""

from __future__ import annotations

from collections.abc import Mapping

FORBIDDEN_EXACT_KEYS = frozenset(
    {
        "SSS_APPROVAL_SIGNING_KEY",
        "SSS_API_BEARER_TOKENS",
        "SSS_EXASOL_PASSWORD",
        "SSS_GITHUB_TOKEN",
        "SSS_MODEL_PROVIDER_KEYS",
    }
)


class UnsafeEnvironmentError(ValueError):
    """Raised when a protected child would receive an administrative secret."""


def build_minimal_environment(
    source: Mapping[str, str],
    *,
    allowed_keys: frozenset[str],
    overrides: Mapping[str, str] | None = None,
) -> dict[str, str]:
    selected = {
        key: value
        for key, value in source.items()
        if key in allowed_keys and key not in FORBIDDEN_EXACT_KEYS
    }
    for key, value in (overrides or {}).items():
        if key in FORBIDDEN_EXACT_KEYS:
            raise UnsafeEnvironmentError(f"protected environment cannot contain {key}")
        if "\x00" in key or "\x00" in value or "=" in key:
            raise UnsafeEnvironmentError("environment override contains invalid characters")
        selected[key] = value
    return selected
