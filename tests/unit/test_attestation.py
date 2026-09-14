from __future__ import annotations

from dataclasses import replace

from sss_core.domain import Decision, EvidenceScores, PolicyDecision
from sss_core.evidence.attestation import attest_decision, canonical_decision_json


def test_decision_attestation_is_canonical_and_sensitive_to_evidence() -> None:
    decision = PolicyDecision(
        decision_id="decision-1",
        request_id="request-1",
        decision=Decision.BLOCK,
        reason_codes=("PACKAGE_NOT_FOUND",),
        scores=EvidenceScores(100, 95, 0),
        policy_version="sss-hackathon-v3",
        expires_at=None,
    )

    first = attest_decision(decision)
    second = attest_decision(decision)
    changed = attest_decision(replace(decision, scores=EvidenceScores(100, 94, 0)))

    assert first == second
    assert len(first) == 64
    assert changed != first
    assert canonical_decision_json(decision).startswith(b'{"decision":"block"')
