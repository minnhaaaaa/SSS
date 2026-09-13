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
    assert "healthcheck" in document["services"]["api"]
    assert agent["depends_on"]["api"]["condition"] == "service_healthy"


def test_public_runtime_images_are_pinned_by_digest() -> None:
    document = yaml.safe_load((ROOT / "infra/docker/demo.compose.yaml").read_text())

    assert "@sha256:" in document["services"]["registry"]["image"]
    assert "@sha256:" in document["services"]["registry-tls"]["image"]


def test_registry_seed_and_unprotected_baseline_are_controlled_and_isolated() -> None:
    document = yaml.safe_load((ROOT / "infra/docker/demo.compose.yaml").read_text())
    seed = document["services"]["registry-seed"]
    baseline = document["services"]["unprotected-agent"]

    assert seed["entrypoint"] == ["/opt/sss/.venv/bin/python"]
    assert seed["command"] == ["/opt/sss/demo/synthetic-package/seed_registry.py"]
    assert seed["networks"] == ["protected"]
    assert "SSS_API_TOKEN" not in seed.get("environment", {})
    assert baseline["entrypoint"] == ["/usr/local/bin/pnpm"]
    assert baseline["command"] == [
        "add",
        "@sss-demo/reserved-synthetic@1.0.0",
        "--registry",
        "https://npm.demo.sss.test",
        "--allow-build=@sss-demo/reserved-synthetic",
    ]
    assert baseline["networks"] == ["protected"]
    assert "SSS_API_TOKEN" not in baseline["environment"]
