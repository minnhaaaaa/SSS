"""Strict approval issuance and consumption schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from sss_core.policy.approvals import ApprovalScope

from sss_api.schemas.guard import PackageIdentityModel
from sss_api.services.approvals import ApprovalGrant


class ApprovalClaimsModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    package: PackageIdentityModel
    version: str = Field(min_length=1, max_length=256)
    registry_origin: str
    artifact_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    project_id: str = Field(min_length=1, max_length=128)
    expires_at: datetime
    nonce: str = Field(min_length=1, max_length=128)
    policy_version: str

    def to_scope(self) -> ApprovalScope:
        return ApprovalScope.from_claims(self.model_dump(mode="json"))


class ApprovalCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    intervention_id: str = Field(min_length=1, max_length=128)
    claims: ApprovalClaimsModel


class ApprovalCreateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    approval_id: str
    token: str
    claims: ApprovalClaimsModel
    single_use: bool = True

    @classmethod
    def from_domain(cls, grant: ApprovalGrant) -> ApprovalCreateResponse:
        return cls(
            approval_id=grant.approval_id,
            token=grant.token,
            claims=ApprovalClaimsModel.model_validate(grant.scope.to_claims()),
        )


class ApprovalConsumeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    token: str = Field(min_length=1, max_length=8192)
    request_id: str = Field(min_length=1, max_length=128)
    expected_nonce: str = Field(min_length=1, max_length=128)


class ApprovalConsumeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    approval_id: str
    consumed: bool
    remaining_uses: int
