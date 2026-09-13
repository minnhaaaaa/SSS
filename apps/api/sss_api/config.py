"""Environment-backed configuration for the API service."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from os import environ


class ConfigurationError(ValueError):
    """Raised when runtime configuration is invalid."""


def _positive_int(values: Mapping[str, str], key: str, default: int) -> int:
    raw = values.get(key, str(default))
    try:
        parsed = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{key} must be an integer") from exc
    if parsed <= 0:
        raise ConfigurationError(f"{key} must be positive")
    return parsed


@dataclass(frozen=True, slots=True)
class ApiSettings:
    environment: str
    policy_version: str
    bearer_tokens: tuple[str, ...]
    max_body_bytes: int
    idempotency_key_max_bytes: int
    sse_heartbeat_seconds: int
    sse_buffer_size: int

    @classmethod
    def from_env(cls, values: Mapping[str, str] | None = None) -> ApiSettings:
        source = environ if values is None else values
        tokens = tuple(
            token.strip()
            for token in source.get("SSS_API_BEARER_TOKENS", "").split(",")
            if token.strip()
        )
        return cls(
            environment=source.get("SSS_ENV", "development"),
            policy_version=source.get("SSS_POLICY_VERSION", "sss-hackathon-v3"),
            bearer_tokens=tokens,
            max_body_bytes=_positive_int(source, "SSS_API_MAX_BODY_BYTES", 1_048_576),
            idempotency_key_max_bytes=_positive_int(source, "SSS_IDEMPOTENCY_KEY_MAX_BYTES", 128),
            sse_heartbeat_seconds=_positive_int(source, "SSS_SSE_HEARTBEAT_SECONDS", 15),
            sse_buffer_size=_positive_int(source, "SSS_SSE_BUFFER_SIZE", 512),
        )
