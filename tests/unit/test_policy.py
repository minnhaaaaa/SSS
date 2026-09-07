from __future__ import annotations

from dataclasses import replace

import pytest
from sss_core.domain import (
    CandidateStatus,
    Decision,
    Ecosystem,
    EvidenceScores,
    InstallRequest,
    PackageIdentity,
)
from sss_core.policy.engine import PolicyContext, PolicyEngine
from sss_core.policy.reasons import ReasonCode
from sss_core.registries.base import RegistryOutcome


def _request() -> InstallRequest:
    return InstallRequest(
        request_id="request-1",
        project_id="project-1",
        agent_family="codex",
        package=PackageIdentity(Ecosystem.NPM, "https://registry.npmjs.org", "demo"),
        version_spec="1.0.0",
        direct_url=None,
        artifact_sha256="a" * 64,
        is_direct=True,
    )


def _context() -> PolicyContext:
    return PolicyContext(
        candidate_status=CandidateStatus.REGISTERED,
        registry_outcome=RegistryOutcome.REGISTERED,
        scores=EvidenceScores(None, 0, 0),
        approved_source=True,
        strict_mode=True,
        interactive=True,
        historical_hallucination=False,
    )


@pytest.mark.parametrize(
    ("context", "decision", "reason"),
    [
        (
            replace(
                _context(),
                candidate_status=CandidateStatus.VERIFIED_ABSENT,
                registry_outcome=RegistryOutcome.ABSENT,
                scores=EvidenceScores(100, 50, 0),
            ),
            Decision.BLOCK,
            ReasonCode.PACKAGE_NOT_FOUND,
        ),
        (
            replace(_context(), registry_outcome=RegistryOutcome.UNKNOWN_NETWORK),
            Decision.BLOCK,
            ReasonCode.ASSESSMENT_UNAVAILABLE,
        ),
        (
            replace(_context(), approved_source=False),
            Decision.BLOCK,
            ReasonCode.UNAPPROVED_SOURCE,
        ),
        (
            replace(
                _context(),
                candidate_status=CandidateStatus.REGISTERED_AFTER_ABSENCE,
                scores=EvidenceScores(100, 95, 75),
                historical_hallucination=True,
            ),
            Decision.BLOCK,
            ReasonCode.REGISTERED_AFTER_HALLUCINATION,
        ),
        (
            _context(),
            Decision.ALLOW,
            ReasonCode.ESTABLISHED_APPROVED,
        ),
    ],
)
def test_policy_hard_rules(
    context: PolicyContext,
    decision: Decision,
    reason: ReasonCode,
) -> None:
    result = PolicyEngine().assess(_request(), context)

    assert result.decision is decision
    assert reason.value in result.reason_codes
    assert result.policy_version == "sss-hackathon-v3"


def test_noninteractive_review_resolves_to_block() -> None:
    context = replace(
        _context(),
        candidate_status=CandidateStatus.REGISTERED_AFTER_ABSENCE,
        scores=EvidenceScores(100, 40, 45),
        interactive=False,
    )

    result = PolicyEngine().assess(_request(), context)

    assert result.decision is Decision.BLOCK
    assert result.reason_codes == (
        ReasonCode.REGISTERED_AFTER_ABSENCE.value,
        ReasonCode.NONINTERACTIVE_REVIEW_BLOCKED.value,
    )
