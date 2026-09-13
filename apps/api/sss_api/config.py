"""Environment-backed configuration for the API service."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from os import environ
from pathlib import Path

from sss_core import POLICY_VERSION, RuntimeMode


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


def _boolean(values: Mapping[str, str], key: str, default: bool) -> bool:
    raw = values.get(key, str(default)).casefold()
    if raw not in {"true", "false"}:
        raise ConfigurationError(f"{key} must be true or false")
    return raw == "true"


@dataclass(frozen=True, slots=True)
class ApiSettings:
    environment: str
    policy_version: str
    bearer_tokens: tuple[str, ...]
    max_body_bytes: int
    idempotency_key_max_bytes: int
    sse_heartbeat_seconds: int
    sse_buffer_size: int
    approval_signing_key: str | None = None
    exasol_required: bool = False
    credentials_file: Path | None = None
    runtime_mode: RuntimeMode = field(init=False)

    def __post_init__(self) -> None:
        environment = self.environment.strip().casefold()
        try:
            runtime_mode = RuntimeMode(environment)
        except ValueError as exc:
            expected = ", ".join(mode.value for mode in RuntimeMode)
            raise ConfigurationError(
                f"SSS_ENV must select an explicit runtime mode: {expected}"
            ) from exc
        object.__setattr__(self, "environment", environment)
        object.__setattr__(self, "runtime_mode", runtime_mode)
        if runtime_mode is RuntimeMode.PRODUCTION:
            self._validate_production()

    def _validate_production(self) -> None:
        if not self.exasol_required:
            raise ConfigurationError("production requires Exasol")
        if self.approval_signing_key is None:
            raise ConfigurationError("production requires an approval signing key")
        if len(self.approval_signing_key.encode()) < 32:
            raise ConfigurationError(
                "production approval signing key must contain at least 32 bytes"
            )
        if "demo" in self.approval_signing_key.casefold():
            raise ConfigurationError("production requires a non-demo signing key")
        if self.credentials_file is None or not self.credentials_file.is_file():
            raise ConfigurationError("production requires an existing credentials file")
        if self.policy_version != POLICY_VERSION:
            raise ConfigurationError(
                f"production policy version must be the expected version {POLICY_VERSION!r}"
            )

    @classmethod
    def from_env(cls, values: Mapping[str, str] | None = None) -> ApiSettings:
        source = environ if values is None else values
        tokens = tuple(
            token.strip()
            for token in source.get("SSS_API_BEARER_TOKENS", "").split(",")
            if token.strip()
        )
        return cls(
            environment=source.get("SSS_ENV", RuntimeMode.PRODUCTION.value),
            policy_version=source.get("SSS_POLICY_VERSION", POLICY_VERSION),
            bearer_tokens=tokens,
            max_body_bytes=_positive_int(source, "SSS_API_MAX_BODY_BYTES", 1_048_576),
            idempotency_key_max_bytes=_positive_int(source, "SSS_IDEMPOTENCY_KEY_MAX_BYTES", 128),
            sse_heartbeat_seconds=_positive_int(source, "SSS_SSE_HEARTBEAT_SECONDS", 15),
            sse_buffer_size=_positive_int(source, "SSS_SSE_BUFFER_SIZE", 512),
            approval_signing_key=source.get("SSS_APPROVAL_SIGNING_KEY") or None,
            exasol_required=_boolean(source, "SSS_EXASOL_REQUIRED", False),
            credentials_file=(
                Path(credentials_file).expanduser()
                if (credentials_file := source.get("SSS_CREDENTIALS_FILE", "").strip())
                else None
            ),
        )
