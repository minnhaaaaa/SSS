from __future__ import annotations

from sss_core.evidence.scoring import (
    AttractivenessInputs,
    PolicyRiskInputs,
    score_absence_confidence,
    score_package_policy_risk,
    score_target_attractiveness,
)


def test_fixed_demo_scores_are_exactly_100_95_75() -> None:
    absence = score_absence_confidence(
        conclusive_absence=True,
        valid_identity=True,
        exclusions_complete=True,
    )
    attractiveness = score_target_attractiveness(
        AttractivenessInputs(
            distinct_verified_runs=46,
            distinct_model_configurations=3,
            distinct_clients=8,
            distinct_public_sources=5,
            distinct_observation_days=11,
            explicit_install_context=True,
        )
    )
    risk = score_package_policy_risk(
        PolicyRiskInputs(
            registered_after_absence=True,
            first_release_age_hours=43 / 60,
            target_attractiveness=attractiveness,
            source_policy_violation=False,
            suspicious_static_finding=False,
        )
    )

    assert (absence, attractiveness, risk) == (100, 95, 75)


def test_inconclusive_absence_has_no_score_and_factors_are_capped() -> None:
    assert (
        score_absence_confidence(
            conclusive_absence=False,
            valid_identity=True,
            exclusions_complete=True,
        )
        is None
    )
    assert score_target_attractiveness(AttractivenessInputs(999, 99, 99, 99, 99, True)) == 100
