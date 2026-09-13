from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).parents[2]


def test_demo_agent_is_isolated_and_has_only_runtime_guard_credentials() -> None:
    document = yaml.safe_load((ROOT / "infra/docker/demo.compose.yaml").read_text())
    agent = document["services"]["protected-agent"]

    assert agent["user"] == "65532:65532"
    assert agent["read_only"] is True
    assert agent["cap_drop"] == ["ALL"]
    assert agent["security_opt"] == ["no-new-privileges:true"]
    assert agent["networks"] == ["protected"]
    assert agent["environment"]["PATH"].startswith("/opt/sss/shims:")
    serialized = yaml.safe_dump(agent)
    assert "/var/run/docker.sock" not in serialized
    for forbidden in (
        "SSS_APPROVAL_SIGNING_KEY",
        "SSS_EXASOL_PASSWORD",
        "SSS_API_BEARER_TOKENS",
        "SSS_CANARY_TOKEN",
    ):
        assert forbidden not in agent["environment"]
    assert document["networks"]["protected"]["internal"] is True


def test_public_runtime_images_are_pinned_by_digest() -> None:
    document = yaml.safe_load((ROOT / "infra/docker/demo.compose.yaml").read_text())

    assert "@sha256:" in document["services"]["registry"]["image"]
    assert "@sha256:" in document["services"]["registry-tls"]["image"]
