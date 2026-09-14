"""Strict authenticated observation-ingestion schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sss_core import Ecosystem, PackageIdentity, RegistryStatus
from sss_core.identity import canonicalize_identity


class ObservationPackage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    ecosystem: Ecosystem
    registry_origin: str = Field(min_length=1, max_length=2048)
    canonical_name: str = Field(min_length=1, max_length=300)

    def canonical(self) -> PackageIdentity:
        return canonicalize_identity(
            self.ecosystem, self.registry_origin, self.canonical_name
        )


class ModelObservationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    observation_id: str = Field(min_length=1, max_length=100)
    package: ObservationPackage
    source_id: str = Field(min_length=1, max_length=200)
    model_configuration_id: str = Field(min_length=1, max_length=100)
    observed_at: datetime
    context_kind: str = Field(min_length=1, max_length=50)
    explicit_install_context: bool


class ClientObservationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    observation_id: str = Field(min_length=1, max_length=100)
    package: ObservationPackage
    client_pseudonym: str = Field(pattern=r"^[a-zA-Z0-9._-]{8,100}$")
    agent_family: str = Field(min_length=1, max_length=100)
    requested_source: str = Field(min_length=1, max_length=50)
    observed_at: datetime


class PublicObservationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    observation_id: str = Field(min_length=1, max_length=100)
    package: ObservationPackage
    public_url_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_kind: Literal["public_manifest", "public_ci_failure"]
    removal_state: str | None = Field(default=None, max_length=50)
    observed_at: datetime


class RegistryObservationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    check_id: str = Field(min_length=1, max_length=100)
    package: ObservationPackage
    endpoint: str = Field(min_length=1, max_length=2048)
    status: RegistryStatus
    http_status: int | None = Field(default=None, ge=100, le=599)
    checked_at: datetime
    response_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    error_class: str | None = Field(default=None, max_length=100)


class ObservationAccepted(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    observation_id: str
    accepted: bool = True
