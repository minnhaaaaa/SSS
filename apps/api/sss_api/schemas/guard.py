"""Strict public schemas for Guard and intervention routes."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from sss_core import Ecosystem, InstallRequest
from sss_core.identity import canonicalize_identity

from sss_api.services.guard import GuardAssessment
from sss_api.services.interventions import Intervention


class PackageIdentityModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ecosystem: Ecosystem
    registry_origin: str
    canonical_name: str


class GuardCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: str = Field(min_length=1, max_length=128)
    project_id: str = Field(min_length=1, max_length=128)
    agent_family: str = Field(min_length=1, max_length=128)
    package: PackageIdentityModel
    version_spec: str | None = Field(default=None, max_length=256)
    direct_url: str | None = Field(default=None, max_length=2048)
    artifact_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    is_direct: bool

    def to_domain(self) -> InstallRequest:
        package = canonicalize_identity(
            self.package.ecosystem,
            self.package.registry_origin,
            self.package.canonical_name,
        )
        return InstallRequest(
            request_id=self.request_id,
            project_id=self.project_id,
            agent_family=self.agent_family,
            package=package,
            version_spec=self.version_spec,
            direct_url=self.direct_url,
            artifact_sha256=self.artifact_sha256,
            is_direct=self.is_direct,
        )


class EvidenceScoresModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    absence_confidence: int | None
    target_attractiveness: int
    package_policy_risk: int


class GuardCheckResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: str
    request_id: str
    decision: str
    reason_codes: tuple[str, ...]
    scores: EvidenceScoresModel
    policy_version: str
    expires_at: datetime | None
    intervention_id: str | None
    child_process_allowed: bool

    @classmethod
    def from_assessment(cls, assessment: GuardAssessment) -> GuardCheckResponse:
        decision = assessment.decision
        return cls(
            decision_id=decision.decision_id,
            request_id=decision.request_id,
            decision=decision.decision.value,
            reason_codes=decision.reason_codes,
            scores=EvidenceScoresModel(
                absence_confidence=decision.scores.absence_confidence,
                target_attractiveness=decision.scores.target_attractiveness,
                package_policy_risk=decision.scores.package_policy_risk,
            ),
            policy_version=decision.policy_version,
            expires_at=decision.expires_at,
            intervention_id=assessment.intervention_id,
            child_process_allowed=assessment.child_process_allowed,
        )


class InterventionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    intervention_id: str
    request: GuardCheckRequest
    decision: GuardCheckResponse
    evidence_labels: tuple[str, ...]
    status: str
    created_at: datetime
    approval_id: str | None

    @classmethod
    def from_domain(cls, item: Intervention) -> InterventionResponse:
        request = GuardCheckRequest(
            request_id=item.request.request_id,
            project_id=item.request.project_id,
            agent_family=item.request.agent_family,
            package=PackageIdentityModel(
                ecosystem=item.request.package.ecosystem,
                registry_origin=item.request.package.registry_origin,
                canonical_name=item.request.package.canonical_name,
            ),
            version_spec=item.request.version_spec,
            direct_url=item.request.direct_url,
            artifact_sha256=item.request.artifact_sha256,
            is_direct=item.request.is_direct,
        )
        assessment = GuardAssessment(
            decision=item.decision,
            intervention_id=item.intervention_id,
            child_process_allowed=False,
            evidence_labels=item.evidence_labels,
        )
        return cls(
            intervention_id=item.intervention_id,
            request=request,
            decision=GuardCheckResponse.from_assessment(assessment),
            evidence_labels=item.evidence_labels,
            status=item.status.value,
            created_at=item.created_at,
            approval_id=item.approval_id,
        )


class InterventionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    items: tuple[InterventionResponse, ...]
