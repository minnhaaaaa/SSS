"""Environment-backed canary configuration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from os import environ
from pathlib import Path


class CanaryConfigurationError(ValueError):
    """Raised when the canary cannot authenticate or persist safely."""


@dataclass(frozen=True, slots=True)
class CanarySettings:
    database_path: Path
    token: str
    marker: str

    @classmethod
    def from_env(cls, values: Mapping[str, str] | None = None) -> CanarySettings:
        source = environ if values is None else values
        database_value = source.get("SSS_CANARY_DATABASE_PATH", "").strip()
        token = source.get("SSS_CANARY_TOKEN", "")
        marker = source.get("SSS_CANARY_MARKER", "")
        if not database_value:
            raise CanaryConfigurationError("SSS_CANARY_DATABASE_PATH is required")
        if not token:
            raise CanaryConfigurationError("SSS_CANARY_TOKEN is required")
        if not marker:
            raise CanaryConfigurationError("SSS_CANARY_MARKER is required")
        return cls(database_path=Path(database_value).expanduser(), token=token, marker=marker)
