from __future__ import annotations

from sss_core.domain import CandidateStatus, EvidenceProvenance
from sss_core.registries.base import RegistryOutcome


def classify_candidate(
    previous: CandidateStatus | None,
    provenance: EvidenceProvenance,
    registry_outcome: RegistryOutcome,
) -> CandidateStatus:
    if registry_outcome is RegistryOutcome.REGISTERED:
        return CandidateStatus.REGISTERED
    if registry_outcome is RegistryOutcome.ABSENT:
        if provenance is EvidenceProvenance.MODEL_PROBE:
            return CandidateStatus.VERIFIED_HALLUCINATION
        return CandidateStatus.VERIFIED_ABSENT
    return previous or CandidateStatus.AMBIGUOUS
