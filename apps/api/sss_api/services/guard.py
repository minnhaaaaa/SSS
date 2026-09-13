"""Policy-backed Guard assessment service."""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

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
from sss_core.evidence.facts import EvidenceFacts
from sss_core.evidence.scoring import (
    AttractivenessInputs,
    PolicyRiskInputs,
    score_absence_confidence,
    score_package_policy_risk,
    score_target_attractiveness,
)

from sss_api.events import EventBroker
from sss_api.services.interventions import InterventionStore


class EvidenceProvider(Protocol):
    def context_for(self, package: PackageIdentity) -> PolicyContext: ...


class DecisionRepository(Protocol):
    def record_decision(
        self,
        request: InstallRequest,
        decision: PolicyDecision,
        *,
        evidence_as_of: datetime,
        evidence_attestation: str,
    ) -> PolicyDecision: ...


class PolicyFactsRepository(Protocol):
    def load_facts(self, package: PackageIdentity) -> EvidenceFacts: ...


class ExasolEvidenceProvider(EvidenceProvider):
    """Convert durable Exasol facts through the canonical scoring functions."""

    def __init__(self, repository: PolicyFactsRepository) -> None:
        self._repository = repository

    def context_for(self, package: PackageIdentity) -> PolicyContext:
        facts = self._repository.load_facts(package)
        return self._context_from_facts(facts)

    def context_with_as_of(
        self, package: PackageIdentity
    ) -> tuple[PolicyContext, datetime]:
        facts = self._repository.load_facts(package)
        return self._context_from_facts(facts), facts.data_as_of

    @staticmethod
    def _context_from_facts(facts: EvidenceFacts) -> PolicyContext:
        attractiveness = score_target_attractiveness(
            AttractivenessInputs(
                facts.distinct_verified_runs,
                facts.distinct_model_configurations,
                facts.distinct_clients,
                facts.distinct_public_sources,
                facts.distinct_observation_days,
                facts.explicit_install_context,
            )
        )
        scores = EvidenceScores(
            score_absence_confidence(
                conclusive_absence=facts.conclusive_absence,
                valid_identity=True,
                exclusions_complete=facts.exclusions_complete,
            ),
            attractiveness,
            score_package_policy_risk(
                PolicyRiskInputs(
                    facts.candidate_status is CandidateStatus.REGISTERED_AFTER_ABSENCE,
                    facts.first_release_age_hours,
                    attractiveness,
                    facts.source_policy_violation,
                    facts.suspicious_static_finding,
                )
            ),
        )
        return PolicyContext(
            candidate_status=facts.candidate_status,
            registry_outcome=facts.registry_outcome,
            scores=scores,
            approved_source=not facts.source_policy_violation,
            strict_mode=True,
            interactive=False,
            historical_hallucination=(
                facts.candidate_status is CandidateStatus.REGISTERED_AFTER_ABSENCE
                and facts.distinct_verified_runs > 0
            ),
        )


@dataclass(frozen=True, slots=True)
class GuardAssessment:
    decision: PolicyDecision
    intervention_id: str | None
    child_process_allowed: bool
    evidence_labels: tuple[str, ...]


class GuardService:
    def __init__(
        self,
        engine: PolicyEngine,
        evidence: EvidenceProvider,
        interventions: InterventionStore,
        event_broker: EventBroker,
        *,
        decision_repository: DecisionRepository | None = None,
    ) -> None:
        self._engine = engine
        self._evidence = evidence
        self._interventions = interventions
        self._event_broker = event_broker
        self._decision_repository = decision_repository
        self._by_request_id: dict[str, GuardAssessment] = {}
        self._by_idempotency_key: dict[str, tuple[InstallRequest, GuardAssessment]] = {}
        self._lock = asyncio.Lock()

    async def check(
        self,
        request: InstallRequest,
        *,
        idempotency_key: str | None = None,
    ) -> GuardAssessment:
        async with self._lock:
            if idempotency_key is not None and idempotency_key in self._by_idempotency_key:
                previous_request, assessment = self._by_idempotency_key[idempotency_key]
                if previous_request != request:
                    raise ValueError("idempotency key was already used for another request")
                return assessment
            existing = self._by_request_id.get(request.request_id)
            if existing is not None:
                if idempotency_key is not None:
                    self._by_idempotency_key[idempotency_key] = (request, existing)
                return existing

            timed_context = getattr(self._evidence, "context_with_as_of", None)
            if callable(timed_context):
                context, evidence_as_of = timed_context(request.package)
            else:
                context = self._evidence.context_for(request.package)
                evidence_as_of = datetime.now(UTC)
            decision = self._engine.assess(request, context)
            if self._decision_repository is not None:
                decision = self._decision_repository.record_decision(
                    request,
                    decision,
                    evidence_as_of=evidence_as_of,
                    evidence_attestation=_attest_evidence(
                        request, context, evidence_as_of
                    ),
                )
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
            assessment = GuardAssessment(
                decision=decision,
                intervention_id=intervention_id,
                child_process_allowed=decision.decision is Decision.ALLOW,
                evidence_labels=labels,
            )
            self._by_request_id[request.request_id] = assessment
            if idempotency_key is not None:
                self._by_idempotency_key[idempotency_key] = (request, assessment)
            return assessment

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


def _attest_evidence(
    request: InstallRequest, context: PolicyContext, data_as_of: datetime
) -> str:
    payload: dict[str, Any] = {
        "request_id": request.request_id,
        "package": {
            "ecosystem": request.package.ecosystem.value,
            "registry_origin": request.package.registry_origin,
            "canonical_name": request.package.canonical_name,
        },
        "candidate_status": context.candidate_status.value,
        "registry_outcome": context.registry_outcome.value,
        "scores": {
            "absence_confidence": context.scores.absence_confidence,
            "target_attractiveness": context.scores.target_attractiveness,
            "package_policy_risk": context.scores.package_policy_risk,
        },
        "approved_source": context.approved_source,
        "historical_hallucination": context.historical_hallucination,
        "data_as_of": data_as_of.astimezone(UTC).isoformat(),
    }
    canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(canonical).hexdigest()
