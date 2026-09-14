"""Validated environment configuration for registry upstreams and limits."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from os import environ

from sss_gateway.artifacts.models import ArchiveLimits
from sss_gateway.security.origins import normalize_origin


class GatewayConfigurationError(ValueError):
    """Raised when gateway configuration cannot fail safely."""


@dataclass(frozen=True, slots=True)
class GatewaySettings:
    upstreams: Mapping[str, str]
    max_artifact_bytes: int
    archive_limits: ArchiveLimits
    connect_timeout_seconds: float
    read_timeout_seconds: float

    @classmethod
    def from_env(cls, values: Mapping[str, str] | None = None) -> GatewaySettings:
        source = environ if values is None else values
        raw = source.get("SSS_GATEWAY_UPSTREAMS_JSON", "")
        if not raw:
            raise GatewayConfigurationError("SSS_GATEWAY_UPSTREAMS_JSON is required")
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise GatewayConfigurationError(
                "SSS_GATEWAY_UPSTREAMS_JSON must be valid JSON"
            ) from exc
        if not isinstance(decoded, dict) or not decoded:
            raise GatewayConfigurationError("at least one named upstream is required")
        upstreams: dict[str, str] = {}
        for name, value in decoded.items():
            if not isinstance(name, str) or not isinstance(value, str):
                raise GatewayConfigurationError("upstream names and origins must be strings")
            upstreams[name.casefold()] = normalize_origin(value)
        max_bytes = _positive_int(source, "SSS_GATEWAY_MAX_ARTIFACT_BYTES", 20 * 1024 * 1024)
        archive_limits = ArchiveLimits(
            max_compressed_bytes=max_bytes,
            max_expanded_bytes=_positive_int(
                source, "SSS_GATEWAY_MAX_EXPANDED_BYTES", 100 * 1024 * 1024
            ),
            max_entries=_positive_int(source, "SSS_GATEWAY_MAX_ARCHIVE_ENTRIES", 10_000),
            max_file_bytes=_positive_int(source, "SSS_GATEWAY_MAX_FILE_BYTES", 5 * 1024 * 1024),
            max_compression_ratio=_positive_float(
                source, "SSS_GATEWAY_MAX_COMPRESSION_RATIO", 200.0
            ),
        )
        return cls(
            upstreams=upstreams,
            max_artifact_bytes=max_bytes,
            archive_limits=archive_limits,
            connect_timeout_seconds=_positive_float(
                source, "SSS_GATEWAY_CONNECT_TIMEOUT_SECONDS", 3.0
            ),
            read_timeout_seconds=_positive_float(source, "SSS_GATEWAY_READ_TIMEOUT_SECONDS", 15.0),
        )


def _positive_int(values: Mapping[str, str], key: str, default: int) -> int:
    try:
        value = int(values.get(key, str(default)))
    except ValueError as exc:
        raise GatewayConfigurationError(f"{key} must be an integer") from exc
    if value <= 0:
        raise GatewayConfigurationError(f"{key} must be positive")
    return value


def _positive_float(values: Mapping[str, str], key: str, default: float) -> float:
    try:
        value = float(values.get(key, str(default)))
    except ValueError as exc:
        raise GatewayConfigurationError(f"{key} must be numeric") from exc
    if value <= 0:
        raise GatewayConfigurationError(f"{key} must be positive")
    return value
