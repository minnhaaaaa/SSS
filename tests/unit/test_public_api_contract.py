from __future__ import annotations


def test_frozen_domain_types_are_importable_from_package_root() -> None:
    from sss_core import (
        POLICY_VERSION,
        CandidateStatus,
        Decision,
        Ecosystem,
        EvidenceProvenance,
        EvidenceScores,
        InstallRequest,
        PackageIdentity,
        PolicyContext,
        PolicyDecision,
        PolicyEngine,
        ReasonCode,
        RegistryStatus,
    )

    assert Ecosystem.NPM.value == "npm"
    assert EvidenceProvenance.MODEL_PROBE.value == "model_probe"
    assert RegistryStatus.UNKNOWN.value == "unknown"
    assert CandidateStatus.REGISTERED_AFTER_ABSENCE.value == "registered_after_absence"
    assert Decision.BLOCK.value == "block"
    assert ReasonCode.NONINTERACTIVE_REVIEW_BLOCKED.value == (
        "NONINTERACTIVE_REVIEW_BLOCKED"
    )
    assert all(
        symbol is not None
        for symbol in (
            PackageIdentity,
            EvidenceScores,
            InstallRequest,
            PolicyDecision,
            PolicyContext,
            PolicyEngine,
        )
    )
    assert POLICY_VERSION == "sss-hackathon-v3"
