from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sss_core.domain import (
    CandidateStatus,
    Decision,
    EvidenceScores,
    InstallRequest,
    PolicyDecision,
)
from sss_core.policy.reasons import ReasonCode
from sss_core.registries.base import RegistryOutcome

POLICY_VERSION = "sss-hackathon-v3"


@dataclass(frozen=True)
class PolicyContext:
    candidate_status: CandidateStatus
    registry_outcome: RegistryOutcome
    scores: EvidenceScores
    approved_source: bool
    strict_mode: bool
    interactive: bool
    historical_hallucination: bool


class PolicyEngine:
    def assess(self, request: InstallRequest, context: PolicyContext) -> PolicyDecision:
        decision, reasons = self._apply_rules(context)
        decision_key = "\0".join(
            (
                request.request_id,
                decision.value,
                *[reason.value for reason in reasons],
                POLICY_VERSION,
            )
        )
        return PolicyDecision(
            decision_id=hashlib.sha256(decision_key.encode()).hexdigest(),
            request_id=request.request_id,
            decision=decision,
            reason_codes=tuple(reason.value for reason in reasons),
            scores=context.scores,
            policy_version=POLICY_VERSION,
            expires_at=None,
        )

    @staticmethod
    def _apply_rules(context: PolicyContext) -> tuple[Decision, tuple[ReasonCode, ...]]:
        if context.registry_outcome is RegistryOutcome.ABSENT:
            return Decision.BLOCK, (ReasonCode.PACKAGE_NOT_FOUND,)
        if context.registry_outcome not in {
            RegistryOutcome.REGISTERED,
            RegistryOutcome.ABSENT,
        }:
            if context.strict_mode:
                return Decision.BLOCK, (ReasonCode.ASSESSMENT_UNAVAILABLE,)
            return PolicyEngine._resolve_review(
                context,
                (ReasonCode.ASSESSMENT_UNAVAILABLE,),
            )
        if not context.approved_source:
            return Decision.BLOCK, (ReasonCode.UNAPPROVED_SOURCE,)
        if context.candidate_status is CandidateStatus.REGISTERED_AFTER_ABSENCE:
            transition_reason = (
                ReasonCode.REGISTERED_AFTER_HALLUCINATION
                if context.historical_hallucination
                else ReasonCode.REGISTERED_AFTER_ABSENCE
            )
            reasons = (transition_reason,)
            if context.scores.target_attractiveness >= 60:
                return Decision.BLOCK, (*reasons, ReasonCode.HIGH_GLOBAL_RECURRENCE)
            return PolicyEngine._resolve_review(context, reasons)
        return Decision.ALLOW, (ReasonCode.ESTABLISHED_APPROVED,)

    @staticmethod
    def _resolve_review(
        context: PolicyContext,
        reasons: tuple[ReasonCode, ...],
    ) -> tuple[Decision, tuple[ReasonCode, ...]]:
        if context.interactive:
            return Decision.REVIEW, reasons
        return Decision.BLOCK, (*reasons, ReasonCode.NONINTERACTIVE_REVIEW_BLOCKED)
