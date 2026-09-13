"""Typed evidence facts used by production policy evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sss_core.domain import CandidateStatus
from sss_core.registries.base import RegistryOutcome


@dataclass(frozen=True, slots=True)
class EvidenceFacts:
    candidate_status: CandidateStatus
    registry_outcome: RegistryOutcome
    conclusive_absence: bool
    exclusions_complete: bool
    distinct_verified_runs: int
    distinct_model_configurations: int
    distinct_clients: int
    distinct_public_sources: int
    distinct_observation_days: int
    explicit_install_context: bool
    first_release_age_hours: float | None
    source_policy_violation: bool
    suspicious_static_finding: bool
    data_as_of: datetime
