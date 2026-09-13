"""Strict evidence-ingestion payloads."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from sss_api.schemas.guard import PackageIdentityModel


class ObservationBase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_id: str = Field(min_length=1, max_length=100)
    package: PackageIdentityModel
    observed_at: datetime
    explicit_install_context: bool
    evidence_label: str = Field(min_length=1, max_length=200)


class ModelObservation(ObservationBase):
    provenance: Literal["model_probe"]
    source_id: str = Field(min_length=1, max_length=200)
    model_configuration_id: str = Field(min_length=1, max_length=100)


class PublicObservation(ObservationBase):
    provenance: Literal["public_manifest", "public_ci_failure"]
    source_id: str = Field(min_length=1, max_length=200)


class ClientObservation(ObservationBase):
    provenance: Literal["agent_install_attempt"]
    client_pseudonym: str = Field(min_length=1, max_length=100)
    agent_family: str = Field(min_length=1, max_length=100)
    telemetry_opt_in: bool

    @model_validator(mode="after")
    def require_opt_in(self) -> ClientObservation:
        if not self.telemetry_opt_in:
            raise ValueError("client observation requires telemetry opt-in")
        return self


class ObservationReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_id: str
    accepted: bool
    observed_at: datetime
