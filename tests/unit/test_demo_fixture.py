from __future__ import annotations

from pathlib import Path

from sss_core.demo import load_demo_fixture

ROOT = Path(__file__).parents[2]


def test_fixed_demo_fixture_derives_the_frozen_recurrence_values() -> None:
    fixture = load_demo_fixture(ROOT / "demo/fixtures/fixed-intelligence.json")
    mentions = fixture.mention_rows()

    model = [row for row in mentions if row["provenance"] == "model_probe"]
    clients = [row for row in mentions if row["provenance"] == "agent_install_attempt"]
    public = [row for row in mentions if row["provenance"] == "public_ci_failure"]

    assert fixture.package.canonical_name == "@sss-demo/reserved-synthetic"
    assert fixture.package.registry_origin == "https://npm.demo.sss.test"
    assert len(model) == 46
    assert len({row["model_configuration_id"] for row in model}) == 3
    assert len({row["observed_at"].date() for row in mentions}) == 11
    assert len(clients) == 8
    assert len({row["source_id"] for row in clients}) == 8
    assert len(public) == 5
    assert fixture.registration_age_minutes == 43
    assert fixture.scores.absence_confidence == 100
    assert fixture.scores.target_attractiveness == 95
    assert fixture.scores.package_policy_risk == 75


def test_fixture_rejects_a_transition_that_changes_registry_origin(tmp_path: Path) -> None:
    path = tmp_path / "fixture.json"
    path.write_text(
        '{"package":{"ecosystem":"npm","registry_origin":"https://one.test",'
        '"canonical_name":"demo"},"registration_origin":"https://two.test",'
        '"verified_model_recommendations":46,"model_configurations":3,'
        '"protected_agent_attempts":8,"observation_days":11,'
        '"public_failed_references":5,"first_absence_at":"2026-09-01T12:00:00Z",'
        '"registered_at":"2026-09-12T12:00:00Z","attack_at":"2026-09-12T12:43:00Z",'
        '"scores":{"absence_confidence":100,"target_attractiveness":95,'
        '"package_policy_risk":75}}',
        encoding="utf-8",
    )

    try:
        load_demo_fixture(path)
    except ValueError as error:
        assert "same registry origin" in str(error)
    else:
        raise AssertionError("origin-changing transition was accepted")
