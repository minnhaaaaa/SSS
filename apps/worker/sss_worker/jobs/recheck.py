from __future__ import annotations

from dataclasses import dataclass

from sss_core.domain import CandidateStatus
from sss_core.registries.base import RegistryEvidence, RegistryOutcome


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
