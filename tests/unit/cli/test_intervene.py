from __future__ import annotations

import pytest
from sss_cli.intervene import run_intervention


class RecordingInterventionClient:
    def __init__(self) -> None:
        self.kept: list[str] = []
        self.approved: list[str] = []

    def list_pending(self) -> tuple[dict[str, object], ...]:
        return (
            {
                "intervention_id": "intervention-demo",
                "request": {
                    "project_id": "project-demo",
                    "package": {
                        "canonical_name": "@sss-demo/reserved-synthetic",
                        "registry_origin": "https://npm.demo.sss.test",
                    },
                    "version_spec": "1.0.0",
                    "artifact_sha256": "b" * 64,
                },
                "decision": {
                    "scores": {
                        "absence_confidence": 100,
                        "target_attractiveness": 95,
                        "package_policy_risk": 75,
                    },
                    "reason_codes": [
                        "REGISTERED_AFTER_HALLUCINATION",
                        "HIGH_GLOBAL_RECURRENCE",
                    ],
                    "policy_version": "sss-hackathon-v3",
                },
                "evidence_labels": [
                    "46 verified model recommendations",
                    "registered 43 minutes ago",
                ],
            },
        )

    def keep_blocked(self, intervention_id: str) -> None:
        self.kept.append(intervention_id)

    def approve_once(self, intervention: dict[str, object]) -> None:
        self.approved.append(str(intervention["intervention_id"]))


@pytest.mark.parametrize("answer", ["", "invalid"])
def test_eof_or_invalid_input_defaults_to_keep_blocked(answer: str) -> None:
    client = RecordingInterventionClient()

    run_intervention(
        client,
        input_line=lambda _prompt: answer,
        write=lambda _line: None,
        once=True,
    )

    assert client.kept == ["intervention-demo"]
    assert client.approved == []


def test_allow_once_uses_the_exact_pending_intervention() -> None:
    client = RecordingInterventionClient()

    run_intervention(
        client,
        input_line=lambda _prompt: "a",
        write=lambda _line: None,
        once=True,
    )

    assert client.approved == ["intervention-demo"]
    assert client.kept == []


def test_inspect_prints_ordered_evidence_then_keeps_blocked() -> None:
    client = RecordingInterventionClient()
    answers = iter(("i", "k"))
    output: list[str] = []

    run_intervention(
        client,
        input_line=lambda _prompt: next(answers),
        write=output.append,
        once=True,
    )

    assert output.index("46 verified model recommendations") < output.index(
        "registered 43 minutes ago"
    )
    assert client.kept == ["intervention-demo"]
