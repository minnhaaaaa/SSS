from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from sss_core.domain import PackageIdentity, RegistryStatus


class RegistryOutcome(StrEnum):
    REGISTERED = "registered"
    ABSENT = "absent"
    UNKNOWN_AUTH = "unknown_auth"
    UNKNOWN_RATE_LIMIT = "unknown_rate_limit"
    UNKNOWN_SERVER = "unknown_server"
    UNKNOWN_NETWORK = "unknown_network"
    UNKNOWN_RESPONSE = "unknown_response"


@dataclass(frozen=True)
class RegistryEvidence:
    package: PackageIdentity
    endpoint: str
    outcome: RegistryOutcome
    registry_status: RegistryStatus
    http_status: int | None
    checked_at: datetime
    response_sha256: str | None
    error_class: str | None
    first_release_at: datetime | None = None


class RegistryOracle(Protocol):
    async def check(self, identity: PackageIdentity) -> RegistryEvidence: ...
