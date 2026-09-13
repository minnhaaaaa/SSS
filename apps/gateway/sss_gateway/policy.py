"""Exact, fail-closed registry path permits for protected sessions."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from os import environ

from sss_gateway.security.paths import validate_gateway_path


class GatewayPermitError(ValueError):
    """Raised when a permit set is absent or malformed."""


@dataclass(frozen=True, slots=True)
class GatewayPermit:
    expected_sha256: str | None


class GatewayPermitSet:
    """Authorize only exact upstream/path pairs frozen for one session."""

    def __init__(self, values: Mapping[str, Mapping[str, str | None]]) -> None:
        permits: dict[tuple[str, str], GatewayPermit] = {}
        for upstream, paths in values.items():
            if not isinstance(upstream, str) or not upstream:
                raise GatewayPermitError("permit upstream names must be non-empty strings")
            if not isinstance(paths, Mapping):
                raise GatewayPermitError("permit paths must be an object")
            for path, digest in paths.items():
                if not isinstance(path, str):
                    raise GatewayPermitError("permit paths must be strings")
                try:
                    safe_path = validate_gateway_path(path)
                except ValueError as exc:
                    raise GatewayPermitError("permit contains an unsafe path") from exc
                if digest is not None and (
                    not isinstance(digest, str)
                    or len(digest) != 64
                    or any(character not in "0123456789abcdef" for character in digest)
                ):
                    raise GatewayPermitError(
                        "artifact permits require a lowercase SHA-256 digest"
                    )
                permits[(upstream.casefold(), safe_path)] = GatewayPermit(digest)
        if not permits:
            raise GatewayPermitError("at least one exact gateway permit is required")
        self._permits = permits

    @classmethod
    def from_env(cls, values: Mapping[str, str] | None = None) -> GatewayPermitSet:
        source = environ if values is None else values
        raw = source.get("SSS_GATEWAY_PERMITS_JSON", "")
        if not raw:
            raise GatewayPermitError("SSS_GATEWAY_PERMITS_JSON is required")
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise GatewayPermitError("SSS_GATEWAY_PERMITS_JSON must be valid JSON") from exc
        if not isinstance(decoded, dict):
            raise GatewayPermitError("SSS_GATEWAY_PERMITS_JSON must be an object")
        return cls(decoded)

    def authorize(self, upstream: str, path: str) -> GatewayPermit:
        try:
            return self._permits[(upstream.casefold(), path)]
        except KeyError as exc:
            raise PermissionError("registry path is not permitted for this session") from exc
