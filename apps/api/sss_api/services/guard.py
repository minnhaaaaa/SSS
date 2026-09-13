"""Policy-backed Guard assessment service."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol

from sss_core import (
    Decision,
    InstallRequest,
    PackageIdentity,
    PolicyContext,
    PolicyDecision,
    PolicyEngine,
)

from sss_api.events import EventBroker
from sss_api.services.interventions import InterventionStore


class EvidenceProvider(Protocol):
    def context_for(self, package: PackageIdentity) -> PolicyContext: ...


class ExasolEvidenceProvider(EvidenceProvider, Protocol):
    """Task-5 boundary for production facts loaded by canonical package identity."""


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
    ) -> None:
        self._engine = engine
        self._evidence = evidence
        self._interventions = interventions
        self._event_broker = event_broker
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

            context = self._evidence.context_for(request.package)
            decision = self._engine.assess(request, context)
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
