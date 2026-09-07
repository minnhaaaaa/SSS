from __future__ import annotations

import pytest
from sss_core.domain import CandidateStatus, EvidenceProvenance
from sss_core.evidence.state import classify_candidate
from sss_core.registries.base import RegistryOutcome


@pytest.mark.parametrize(
    ("provenance", "expected"),
    [
        (EvidenceProvenance.MODEL_PROBE, CandidateStatus.VERIFIED_HALLUCINATION),
        (EvidenceProvenance.PUBLIC_MANIFEST, CandidateStatus.VERIFIED_ABSENT),
        (EvidenceProvenance.PUBLIC_CI_FAILURE, CandidateStatus.VERIFIED_ABSENT),
        (EvidenceProvenance.AGENT_INSTALL_ATTEMPT, CandidateStatus.VERIFIED_ABSENT),
    ],
)
def test_only_direct_model_evidence_can_be_verified_hallucination(
    provenance: EvidenceProvenance,
    expected: CandidateStatus,
) -> None:
    assert classify_candidate(None, provenance, RegistryOutcome.ABSENT) is expected


def test_unknown_registry_result_retains_previous_state() -> None:
    assert (
        classify_candidate(
            CandidateStatus.VERIFIED_HALLUCINATION,
            EvidenceProvenance.MODEL_PROBE,
            RegistryOutcome.UNKNOWN_NETWORK,
        )
        is CandidateStatus.VERIFIED_HALLUCINATION
    )
