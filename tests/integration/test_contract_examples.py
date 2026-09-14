from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import yaml
from sss_core.domain import CandidateStatus, Decision, EvidenceProvenance, RegistryStatus
from sss_core.policy.engine import POLICY_VERSION
from sss_core.policy.reasons import ReasonCode

ROOT = Path(__file__).parents[2]
EXAMPLES = ROOT / "docs/contracts/examples"


def _load(name: str) -> dict[str, object]:
    return cast(dict[str, object], json.loads((EXAMPLES / name).read_text(encoding="utf-8")))


def test_shared_contract_delivers_every_required_example() -> None:
    expected = {
        "observation-model.json",
        "observation-public.json",
        "observation-client.json",
        "registry-check.json",
        "package-detail.json",
        "radar-private.json",
        "guard-request.json",
        "guard-decision.json",
        "attempt.json",
        "approval-create-request.json",
        "approval-create-response.json",
        "approval-consume-request.json",
        "approval-consume-response.json",
        "radar-public-aggregate.json",
    }

    assert {path.name for path in EXAMPLES.glob("*.json")} == expected


def test_examples_use_frozen_semantics_and_do_not_leak_private_names_publicly() -> None:
    model = _load("observation-model.json")
    public = _load("observation-public.json")
    client = _load("observation-client.json")
    registry = _load("registry-check.json")
    detail = _load("package-detail.json")
    decision = _load("guard-decision.json")
    aggregate = _load("radar-public-aggregate.json")

    assert model["provenance"] == EvidenceProvenance.MODEL_PROBE.value
    assert public["provenance"] == EvidenceProvenance.PUBLIC_CI_FAILURE.value
    assert client["provenance"] == EvidenceProvenance.AGENT_INSTALL_ATTEMPT.value
    assert registry["status"] in {status.value for status in RegistryStatus}
    assert detail["candidate_status"] in {status.value for status in CandidateStatus}
    assert decision["decision"] in {value.value for value in Decision}
    assert decision["policy_version"] == POLICY_VERSION
    reason_codes = decision["reason_codes"]
    assert isinstance(reason_codes, list)
    assert set(reason_codes) <= {reason.value for reason in ReasonCode}
    assert decision["scores"] == {
        "absence_confidence": 100,
        "target_attractiveness": 95,
        "package_policy_risk": 75,
    }
    assert "canonical_name" not in aggregate
    assert "package" not in aggregate


def test_openapi_handoff_references_every_frozen_json_example() -> None:
    document = yaml.safe_load(
        (ROOT / "docs/contracts/openapi-components.yaml").read_text(encoding="utf-8")
    )

    assert document["info"]["version"] == POLICY_VERSION
    values = document["components"]["examples"]
    assert {
        example["externalValue"].removeprefix("./examples/") for example in values.values()
    } == {path.name for path in EXAMPLES.glob("*.json")}
