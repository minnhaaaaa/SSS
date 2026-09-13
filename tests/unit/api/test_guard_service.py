from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sss_api.events import EventBroker
from sss_api.services.approvals import ApprovalError, ApprovalService
from sss_api.services.guard import ExasolDemoEvidenceProvider, GuardService
from sss_api.services.interventions import InterventionStatus, InterventionStore
from sss_core import (
    CandidateStatus,
    Decision,
    Ecosystem,
    EvidenceScores,
    InstallRequest,
    PackageIdentity,
    PolicyContext,
    PolicyEngine,
)
from sss_core.demo import load_demo_fixture
from sss_core.policy.approvals import ApprovalScope
from sss_core.registries.base import RegistryOutcome


class FixedEvidenceProvider:
    def context_for(self, package: PackageIdentity) -> PolicyContext:
        assert package.canonical_name == "@sss-demo/reserved-synthetic"
        return PolicyContext(
            candidate_status=CandidateStatus.REGISTERED_AFTER_ABSENCE,
            registry_outcome=RegistryOutcome.REGISTERED,
            scores=EvidenceScores(100, 95, 75),
            approved_source=True,
            strict_mode=True,
            interactive=False,
            historical_hallucination=True,
        )


def _request() -> InstallRequest:
    return InstallRequest(
        request_id="req-demo-001",
        project_id="project-demo",
        agent_family="codex",
        package=PackageIdentity(
            ecosystem=Ecosystem.NPM,
            registry_origin="https://npm.demo.sss.test",
            canonical_name="@sss-demo/reserved-synthetic",
        ),
        version_spec="1.0.0",
        direct_url=None,
        artifact_sha256="b" * 64,
        is_direct=True,
    )


async def test_block_creates_one_pending_intervention_and_event() -> None:
    broker = EventBroker(capacity=8)
    store = InterventionStore()
    service = GuardService(PolicyEngine(), FixedEvidenceProvider(), store, broker)

    assessment = await service.check(_request())

    assert assessment.decision.decision is Decision.BLOCK
    assert assessment.decision.reason_codes == (
        "REGISTERED_AFTER_HALLUCINATION",
        "HIGH_GLOBAL_RECURRENCE",
    )
    assert assessment.decision.scores == EvidenceScores(100, 95, 75)
    assert assessment.intervention_id == assessment.decision.decision_id
    assert assessment.child_process_allowed is False
    pending = store.list_pending()
    assert len(pending) == 1
    assert pending[0].status is InterventionStatus.PENDING
    events = broker.snapshot()
    assert len(events) == 1
    assert events[0].event_type == "install.blocked"
    assert events[0].payload["intervention_id"] == assessment.intervention_id


async def test_rechecking_same_request_does_not_duplicate_intervention() -> None:
    broker = EventBroker(capacity=8)
    store = InterventionStore()
    service = GuardService(PolicyEngine(), FixedEvidenceProvider(), store, broker)

    first = await service.check(_request())
    second = await service.check(_request())

    assert second == first
    assert len(store.list_pending()) == 1
    assert len(broker.snapshot()) == 1


async def test_exact_scope_approval_allows_one_guard_retry_only() -> None:
    broker = EventBroker(capacity=8)
    store = InterventionStore()
    approvals = ApprovalService(signing_key=b"a" * 32)
    service = GuardService(
        PolicyEngine(), FixedEvidenceProvider(), store, broker, approval_service=approvals
    )
    request = _request()
    first = await service.check(request, idempotency_key=request.request_id)
    assert first.intervention_id is not None
    nonce = "retry-once"
    grant = approvals.issue(
        intervention_id=first.intervention_id,
        request=request,
        scope=ApprovalScope(
            package=request.package,
            version=request.version_spec or "",
            registry_origin=request.package.registry_origin,
            artifact_sha256=request.artifact_sha256 or "",
            project_id=request.project_id,
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
            nonce=nonce,
            policy_version="sss-hackathon-v3",
        ),
    )

    allowed = await service.check(
        request,
        idempotency_key=request.request_id,
        approval_token=grant.token,
        approval_nonce=nonce,
    )

    assert allowed.decision.decision is Decision.ALLOW
    assert allowed.decision.decision_id != first.decision.decision_id
    assert allowed.child_process_allowed
    assert "EXACT_SCOPE_APPROVAL" in allowed.decision.reason_codes
    assert broker.snapshot()[-1].event_type == "approval.consumed"
    with pytest.raises(ApprovalError, match="already been consumed"):
        await service.check(
            request,
            idempotency_key=request.request_id,
            approval_token=grant.token,
            approval_nonce=nonce,
        )
    assert (await service.check(request)).decision.decision is Decision.BLOCK


class FixedRadarRepository:
    def load_evidence(self, *, ecosystem: str, origin: str, name: str) -> dict[str, object]:
        return {
            "ECOSYSTEM": ecosystem,
            "REGISTRY_ORIGIN": origin,
            "CANONICAL_NAME": name,
            "STATUS": "registered_after_absence",
            "VERIFIED_MODEL_RECOMMENDATIONS": 46,
            "MODEL_CONFIGURATIONS": 3,
            "PROTECTED_AGENT_ATTEMPTS": 8,
            "PUBLIC_FAILED_REFERENCES": 5,
            "OBSERVATION_DAYS": 11,
            "HAS_EXPLICIT_CONTEXT": 1,
            "FIRST_REGISTRATION_AT": None,
            "SOURCE_POLICY_VIOLATION": False,
            "SUSPICIOUS_STATIC_FINDING": False,
        }


def test_exasol_provider_requires_the_frozen_radar_row() -> None:
    fixture = load_demo_fixture(Path(__file__).parents[3] / "demo/fixtures/fixed-intelligence.json")
    provider = ExasolDemoEvidenceProvider(fixture, FixedRadarRepository())

    context = provider.context_for(fixture.package)

    assert context.registry_outcome is RegistryOutcome.REGISTERED
    assert context.scores == EvidenceScores(100, 95, 75)
    assert context.historical_hallucination is True
