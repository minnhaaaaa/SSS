from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from sss_core.domain import CandidateStatus, Ecosystem, PackageIdentity
from sss_core.registries.base import RegistryEvidence, RegistryOracle, RegistryOutcome


@dataclass(frozen=True)
class TransitionResult:
    status: CandidateStatus
    historical_absence: RegistryEvidence
    registration: RegistryEvidence | None


class TransitionDetector:
    def detect(
        self,
        historical_absence: RegistryEvidence,
        current: RegistryEvidence,
    ) -> TransitionResult:
        if historical_absence.outcome is not RegistryOutcome.ABSENT:
            raise ValueError("transition detection requires conclusive historical absence")
        if historical_absence.package != current.package:
            raise ValueError("registry evidence identities must match")
        if (
            current.outcome is RegistryOutcome.REGISTERED
            and current.first_release_at is not None
            and current.first_release_at > historical_absence.checked_at
        ):
            return TransitionResult(
                CandidateStatus.REGISTERED_AFTER_ABSENCE,
                historical_absence,
                current,
            )
        if current.outcome is RegistryOutcome.REGISTERED:
            return TransitionResult(
                CandidateStatus.REGISTERED,
                historical_absence,
                current,
            )
        status = CandidateStatus.VERIFIED_ABSENT
        return TransitionResult(status, historical_absence, None)


class MemoryRecheckSink:
    def __init__(self) -> None:
        self.evidence: dict[str, RegistryEvidence] = {}

    def record(self, evidence: RegistryEvidence) -> bool:
        key = evidence.response_sha256 or hashlib.sha256(
            f"{evidence.package}:{evidence.checked_at.isoformat()}:{evidence.outcome}".encode()
        ).hexdigest()
        if key in self.evidence:
            return False
        self.evidence[key] = evidence
        return True


async def recheck_watchlist(
    identities: Sequence[PackageIdentity],
    oracles: Mapping[Ecosystem, RegistryOracle],
    sink: MemoryRecheckSink,
) -> int:
    new_evidence = 0
    for identity in dict.fromkeys(identities):
        evidence = await oracles[identity.ecosystem].check(identity)
        new_evidence += sink.record(evidence)
    return new_evidence
