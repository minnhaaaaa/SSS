from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from sss_core.domain import Ecosystem, InstallRequest, PackageIdentity
from sss_core.identity import canonicalize_identity

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CLAIMS = {
    "package",
    "version",
    "registry_origin",
    "artifact_sha256",
    "project_id",
    "expires_at",
    "nonce",
    "policy_version",
}
_PACKAGE_CLAIMS = {"ecosystem", "registry_origin", "canonical_name"}


def _string_claim(values: Mapping[str, object], name: str) -> str:
    value = values[name]
    if not isinstance(value, str):
        raise ValueError("approval and package claim values must be strings")
    return value


@dataclass(frozen=True)
class ApprovalScope:
    package: PackageIdentity
    version: str
    registry_origin: str
    artifact_sha256: str
    project_id: str
    expires_at: datetime
    nonce: str
    policy_version: str

    def __post_init__(self) -> None:
        if self.registry_origin != self.package.registry_origin:
            raise ValueError("registry_origin must match package identity")
        if not _SHA256.fullmatch(self.artifact_sha256):
            raise ValueError("artifact_sha256 must be a lowercase SHA-256 hex digest")
        if not self.version or not self.project_id or not self.nonce:
            raise ValueError("version, project_id, and nonce are required")
        if self.expires_at.tzinfo is None:
            raise ValueError("expires_at must include a timezone")
        if self.policy_version != "sss-hackathon-v3":
            raise ValueError("approval scope policy version is not active")

    def to_claims(self) -> dict[str, object]:
        expires_at = self.expires_at.astimezone(UTC).isoformat().replace("+00:00", "Z")
        return {
            "package": {
                "ecosystem": self.package.ecosystem.value,
                "registry_origin": self.package.registry_origin,
                "canonical_name": self.package.canonical_name,
            },
            "version": self.version,
            "registry_origin": self.registry_origin,
            "artifact_sha256": self.artifact_sha256,
            "project_id": self.project_id,
            "expires_at": expires_at,
            "nonce": self.nonce,
            "policy_version": self.policy_version,
        }

    @classmethod
    def from_claims(cls, claims: Mapping[str, object]) -> ApprovalScope:
        if set(claims) != _CLAIMS:
            raise ValueError("approval claims must contain exactly the frozen claim set")
        package_claims = claims["package"]
        if not isinstance(package_claims, Mapping) or set(package_claims) != _PACKAGE_CLAIMS:
            raise ValueError("package claims must contain exactly ecosystem, origin, and name")
        scalar_claims = (
            "version",
            "registry_origin",
            "artifact_sha256",
            "project_id",
            "expires_at",
            "nonce",
            "policy_version",
        )
        claim_values = {name: _string_claim(claims, name) for name in scalar_claims}
        package_values = {
            name: _string_claim(package_claims, name) for name in _PACKAGE_CLAIMS
        }
        expires_value = claim_values["expires_at"]
        expires_at = datetime.fromisoformat(expires_value.replace("Z", "+00:00"))
        package = canonicalize_identity(
            Ecosystem(package_values["ecosystem"]),
            package_values["registry_origin"],
            package_values["canonical_name"],
        )
        return cls(
            package=package,
            version=claim_values["version"],
            registry_origin=claim_values["registry_origin"],
            artifact_sha256=claim_values["artifact_sha256"],
            project_id=claim_values["project_id"],
            expires_at=expires_at,
            nonce=claim_values["nonce"],
            policy_version=claim_values["policy_version"],
        )

    def covers(self, request: InstallRequest, *, now: datetime) -> bool:
        return (
            now < self.expires_at
            and request.package == self.package
            and request.package.registry_origin == self.registry_origin
            and request.version_spec == self.version
            and request.artifact_sha256 == self.artifact_sha256
            and request.project_id == self.project_id
            and request.direct_url is None
        )


class ApprovalConsumer(Protocol):
    """Boundary implemented by Teammate 2's signer and one-time grant store."""

    def consume(self, token: str, expected_scope: ApprovalScope) -> bool: ...
