"""Policy-backed Guard assessment service."""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from threading import RLock
from typing import Protocol

from sss_core import (
    CandidateStatus,
    Decision,
    EvidenceScores,
    InstallRequest,
    PackageIdentity,
    PolicyContext,
    PolicyDecision,
    PolicyEngine,
)
from sss_core.demo import FixedDemoFixture
from sss_core.evidence.scoring import (
    AttractivenessInputs,
    PolicyRiskInputs,
    score_package_policy_risk,
    score_target_attractiveness,
)
from sss_core.registries.base import RegistryOutcome

from sss_api.events import EventBroker
from sss_api.services.approvals import ApprovalService
from sss_api.services.interventions import InterventionStore


class EvidenceProvider(Protocol):
    def context_for(self, package: PackageIdentity) -> PolicyContext: ...


class DecisionSink(Protocol):
    def store(self, request: InstallRequest, decision: PolicyDecision) -> None: ...


class NoopDecisionSink:
    def store(self, request: InstallRequest, decision: PolicyDecision) -> None:
        del request, decision


class RadarRepository(Protocol):
    def load_evidence(self, *, ecosystem: str, origin: str, name: str) -> dict[str, object]: ...


@dataclass(frozen=True, slots=True)
class GuardAssessment:
    decision: PolicyDecision
    intervention_id: str | None
    child_process_allowed: bool
    evidence_labels: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GuardRecord:
    """A decision created from an install request received by this process."""

    request: InstallRequest
    assessment: GuardAssessment
    decided_at: datetime


class FixedDemoEvidenceProvider:
    def __init__(self, fixture: FixedDemoFixture) -> None:
        self._fixture = fixture

    def context_for(self, package: PackageIdentity) -> PolicyContext:
        if package == self._fixture.package:
            return PolicyContext(
                candidate_status=CandidateStatus.REGISTERED_AFTER_ABSENCE,
                registry_outcome=RegistryOutcome.REGISTERED,
                scores=self._fixture.scores,
                approved_source=True,
                strict_mode=True,
                interactive=False,
                historical_hallucination=True,
            )
        return PolicyContext(
            candidate_status=CandidateStatus.AMBIGUOUS,
            registry_outcome=RegistryOutcome.UNKNOWN_NETWORK,
            scores=EvidenceScores(None, 0, 0),
            approved_source=False,
            strict_mode=True,
            interactive=False,
            historical_hallucination=False,
        )


class FailClosedEvidenceProvider:
    """Return an unavailable context when required evidence storage is not ready."""

    def context_for(self, package: PackageIdentity) -> PolicyContext:
        del package
        return PolicyContext(
            candidate_status=CandidateStatus.AMBIGUOUS,
            registry_outcome=RegistryOutcome.UNKNOWN_RESPONSE,
            scores=EvidenceScores(None, 0, 0),
            approved_source=False,
            strict_mode=True,
            interactive=False,
            historical_hallucination=False,
        )


class ExasolDemoEvidenceProvider:
    """Require Exasol's private Radar row before returning the frozen demo assessment."""

    def __init__(self, fixture: FixedDemoFixture, repository: RadarRepository) -> None:
        self._fixture = fixture
        self._repository = repository
        self._fallback = FixedDemoEvidenceProvider(fixture)

    def context_for(self, package: PackageIdentity) -> PolicyContext:
        if package != self._fixture.package:
            return self._fallback.context_for(package)
        row = self._repository.load_evidence(
            ecosystem=package.ecosystem.value,
            origin=package.registry_origin,
            name=package.canonical_name,
        )
        expected = {
            "ECOSYSTEM": "npm",
            "REGISTRY_ORIGIN": "https://npm.demo.sss.test",
            "CANONICAL_NAME": "@sss-demo/reserved-synthetic",
            "STATUS": "registered_after_absence",
            "VERIFIED_MODEL_RECOMMENDATIONS": 46,
            "MODEL_CONFIGURATIONS": 3,
            "PROTECTED_AGENT_ATTEMPTS": 8,
            "PUBLIC_FAILED_REFERENCES": 5,
            "OBSERVATION_DAYS": 11,
        }
        if any(row.get(key) != value for key, value in expected.items()):
            return PolicyContext(
                candidate_status=CandidateStatus.AMBIGUOUS,
                registry_outcome=RegistryOutcome.UNKNOWN_RESPONSE,
                scores=EvidenceScores(None, 0, 0),
                approved_source=False,
                strict_mode=True,
                interactive=False,
                historical_hallucination=False,
            )
        return self._fallback.context_for(package)


class ExasolEvidenceProvider:
    """Translate a private Exasol Radar row into deterministic policy context."""

    def __init__(self, repository: RadarRepository) -> None:
        self._repository = repository

    def context_for(self, package: PackageIdentity) -> PolicyContext:
        row = self._repository.load_evidence(
            ecosystem=package.ecosystem.value,
            origin=package.registry_origin,
            name=package.canonical_name,
        )
        if not row:
            return PolicyContext(
                candidate_status=CandidateStatus.AMBIGUOUS,
                registry_outcome=RegistryOutcome.UNKNOWN_RESPONSE,
                scores=EvidenceScores(None, 0, 0),
                approved_source=False,
                strict_mode=True,
                interactive=False,
                historical_hallucination=False,
            )
        try:
            status = CandidateStatus(str(row["STATUS"]))
            attractiveness = score_target_attractiveness(
                AttractivenessInputs(
                    distinct_verified_runs=self._integer(row["VERIFIED_MODEL_RECOMMENDATIONS"]),
                    distinct_model_configurations=self._integer(row["MODEL_CONFIGURATIONS"]),
                    distinct_clients=self._integer(row["PROTECTED_AGENT_ATTEMPTS"]),
                    distinct_public_sources=self._integer(row["PUBLIC_FAILED_REFERENCES"]),
                    distinct_observation_days=self._integer(row["OBSERVATION_DAYS"]),
                    explicit_install_context=bool(row["HAS_EXPLICIT_CONTEXT"]),
                )
            )
        except (KeyError, TypeError, ValueError):
            return self._unavailable()
        registered_after_absence = status is CandidateStatus.REGISTERED_AFTER_ABSENCE
        policy_risk = score_package_policy_risk(
            PolicyRiskInputs(
                registered_after_absence=registered_after_absence,
                first_release_age_hours=self._release_age_hours(row["FIRST_REGISTRATION_AT"]),
                target_attractiveness=attractiveness,
                source_policy_violation=bool(row["SOURCE_POLICY_VIOLATION"]),
                suspicious_static_finding=bool(row["SUSPICIOUS_STATIC_FINDING"]),
            )
        )
        if status in {CandidateStatus.REGISTERED, CandidateStatus.REGISTERED_AFTER_ABSENCE}:
            registry_outcome = RegistryOutcome.REGISTERED
        elif status in {CandidateStatus.VERIFIED_ABSENT, CandidateStatus.VERIFIED_HALLUCINATION}:
            registry_outcome = RegistryOutcome.ABSENT
        else:
            registry_outcome = RegistryOutcome.UNKNOWN_RESPONSE
        return PolicyContext(
            candidate_status=status,
            registry_outcome=registry_outcome,
            scores=EvidenceScores(
                100
                if status
                in {
                    CandidateStatus.VERIFIED_ABSENT,
                    CandidateStatus.VERIFIED_HALLUCINATION,
                    CandidateStatus.REGISTERED_AFTER_ABSENCE,
                }
                else None,
                attractiveness,
                policy_risk,
            ),
            approved_source=True,
            strict_mode=True,
            interactive=False,
            historical_hallucination=(
                status
                in {
                    CandidateStatus.VERIFIED_HALLUCINATION,
                    CandidateStatus.REGISTERED_AFTER_ABSENCE,
                }
            ),
        )

    @staticmethod
    def _unavailable() -> PolicyContext:
        return PolicyContext(
            candidate_status=CandidateStatus.AMBIGUOUS,
            registry_outcome=RegistryOutcome.UNKNOWN_RESPONSE,
            scores=EvidenceScores(None, 0, 0),
            approved_source=False,
            strict_mode=True,
            interactive=False,
            historical_hallucination=False,
        )

    @staticmethod
    def _integer(value: object) -> int:
        return int(str(value))

    @staticmethod
    def _release_age_hours(value: object) -> float | None:
        if not isinstance(value, datetime):
            return None
        registered = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        return max(0.0, (datetime.now(UTC) - registered).total_seconds() / 3600)


class GuardService:
    def __init__(
        self,
        engine: PolicyEngine,
        evidence: EvidenceProvider,
        interventions: InterventionStore,
        event_broker: EventBroker,
        decision_sink: DecisionSink | None = None,
        approval_service: ApprovalService | None = None,
    ) -> None:
        self._engine = engine
        self._evidence = evidence
        self._interventions = interventions
        self._event_broker = event_broker
        self._decision_sink = decision_sink or NoopDecisionSink()
        self._approval_service = approval_service
        self._by_request_id: dict[str, GuardAssessment] = {}
        self._by_idempotency_key: dict[str, tuple[InstallRequest, GuardAssessment]] = {}
        self._lock = asyncio.Lock()
        self._records: list[GuardRecord] = []
        self._records_lock = RLock()

    async def check(
        self,
        request: InstallRequest,
        *,
        idempotency_key: str | None = None,
        approval_token: str | None = None,
        approval_nonce: str | None = None,
    ) -> GuardAssessment:
        async with self._lock:
            if (
                approval_token is None
                and idempotency_key is not None
                and idempotency_key in self._by_idempotency_key
            ):
                previous_request, assessment = self._by_idempotency_key[idempotency_key]
                if previous_request != request:
                    raise ValueError("idempotency key was already used for another request")
                return assessment
            existing = (
                None if approval_token is not None else self._by_request_id.get(request.request_id)
            )
            if existing is not None:
                if idempotency_key is not None:
                    self._by_idempotency_key[idempotency_key] = (request, existing)
                return existing

            context = self._evidence.context_for(request.package)
            decision = self._engine.assess(request, context)
            approval_id: str | None = None
            if approval_token is not None:
                if approval_nonce is None:
                    raise ValueError("approval nonce is required with an approval token")
                if self._approval_service is None:
                    raise ValueError("approval verification is not configured")
                grant = self._approval_service.consume(
                    token=approval_token,
                    request_id=request.request_id,
                    expected_nonce=approval_nonce,
                    request=request,
                )
                approval_id = grant.approval_id
                decision = replace(
                    decision,
                    decision_id=hashlib.sha256(
                        f"{decision.decision_id}\0{approval_id}\0allow".encode()
                    ).hexdigest(),
                    decision=Decision.ALLOW,
                    reason_codes=(*decision.reason_codes, "EXACT_SCOPE_APPROVAL"),
                )
            self._decision_sink.store(request, decision)
            labels = self._evidence_labels(context)
            intervention_id: str | None = None
            if decision.decision is not Decision.ALLOW:
                intervention = self._interventions.create(
                    request,
                    decision,
                    evidence_labels=labels,
                )
                intervention_id = intervention.intervention_id
                await self._event_broker.publish(
                    "install.blocked",
                    {
                        "intervention_id": intervention_id,
                        "decision_id": decision.decision_id,
                        "request_id": request.request_id,
                        "decision": decision.decision.value,
                        "reason_codes": list(decision.reason_codes),
                        "scores": {
                            "absence_confidence": decision.scores.absence_confidence,
                            "target_attractiveness": decision.scores.target_attractiveness,
                            "package_policy_risk": decision.scores.package_policy_risk,
                        },
                    },
                )
            elif approval_id is not None:
                await self._event_broker.publish(
                    "approval.consumed",
                    {
                        "approval_id": approval_id,
                        "decision_id": decision.decision_id,
                        "request_id": request.request_id,
                    },
                )
            assessment = GuardAssessment(
                decision=decision,
                intervention_id=intervention_id,
                child_process_allowed=decision.decision is Decision.ALLOW,
                evidence_labels=labels,
            )
            with self._records_lock:
                self._records.append(
                    GuardRecord(
                        request=request,
                        assessment=assessment,
                        decided_at=datetime.now(UTC),
                    )
                )
            if approval_id is None:
                self._by_request_id[request.request_id] = assessment
                if idempotency_key is not None:
                    self._by_idempotency_key[idempotency_key] = (request, assessment)
            return assessment

    def records(self) -> tuple[GuardRecord, ...]:
        """Return decisions produced from real requests, newest first."""
        with self._records_lock:
            return tuple(reversed(self._records))

    @staticmethod
    def _evidence_labels(context: PolicyContext) -> tuple[str, ...]:
        labels = [
            f"Verified absence confidence: {context.scores.absence_confidence}",
            f"Global target attractiveness: {context.scores.target_attractiveness}",
            f"Pre-execution package risk: {context.scores.package_policy_risk}",
        ]
        if context.historical_hallucination:
            labels.append("Registered after verified model hallucination")
        return tuple(labels)
