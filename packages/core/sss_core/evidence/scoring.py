from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class AttractivenessInputs:
    distinct_verified_runs: int
    distinct_model_configurations: int
    distinct_clients: int
    distinct_public_sources: int
    distinct_observation_days: int
    explicit_install_context: bool


@dataclass(frozen=True)
class PolicyRiskInputs:
    registered_after_absence: bool
    first_release_age_hours: float | None
    target_attractiveness: int
    source_policy_violation: bool
    suspicious_static_finding: bool


def score_absence_confidence(
    *,
    conclusive_absence: bool,
    valid_identity: bool,
    exclusions_complete: bool,
) -> int | None:
    if conclusive_absence and valid_identity and exclusions_complete:
        return 100
    return None


def _configuration_points(count: int) -> int:
    if count <= 0:
        return 0
    if count == 1:
        return 10
    if count == 2:
        return 15
    return 20


def score_target_attractiveness(inputs: AttractivenessInputs) -> int:
    return min(
        100,
        min(35, max(0, inputs.distinct_verified_runs))
        + _configuration_points(inputs.distinct_model_configurations)
        + min(20, math.floor(max(0, inputs.distinct_clients) * 2.5))
        + min(10, max(0, inputs.distinct_public_sources))
        + min(10, max(0, inputs.distinct_observation_days))
        + (5 if inputs.explicit_install_context else 0),
    )


def score_package_policy_risk(inputs: PolicyRiskInputs) -> int:
    score = 45 if inputs.registered_after_absence else 0
    if inputs.first_release_age_hours is not None and 0 <= inputs.first_release_age_hours <= 72:
        score += 15
    if inputs.target_attractiveness >= 60:
        score += 15
    if inputs.source_policy_violation:
        score += 15
    if inputs.suspicious_static_finding:
        score += 10
    return min(100, score)
