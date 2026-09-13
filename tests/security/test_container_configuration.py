from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = ROOT / "infra" / "docker" / "compose.enforcement.yaml"
PROTECTED_COMPOSE_FILE = ROOT / "infra" / "docker" / "compose.protected.yaml"


def _compose_config() -> dict[str, Any]:
    docker_executable = shutil.which("docker")
    if docker_executable is None:
        pytest.skip("Docker CLI is unavailable")
    environment = {
        **os.environ,
        "SSS_PYTHON_BASE_IMAGE": "local-python-test-image",
        "SSS_UV_VERSION": "local-test-version",
        "SSS_AGENT_BASE_IMAGE": "local-agent-test-image",
        "SSS_API_BEARER_TOKENS": "local-configuration-token",
        "SSS_GATEWAY_UPSTREAMS_JSON": '{"npm":"https://registry.example.test"}',
        "SSS_CANARY_TOKEN": "local-canary-token",
        "SSS_PROJECT_PATH": str(ROOT),
    }
    completed = subprocess.run(
        [docker_executable, "compose", "-f", str(COMPOSE_FILE), "config", "--format", "json"],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return json.loads(completed.stdout)


def _protected_compose_config() -> dict[str, Any]:
    docker_executable = shutil.which("docker")
    if docker_executable is None:
        pytest.skip("Docker CLI is unavailable")
    environment = {
        **os.environ,
        "SSS_AGENT_IMAGE": "local-agent-test-image",
        "SSS_API_URL": "http://api:8000",
        "SSS_GATEWAY_URL": "http://gateway:8080",
        "SSS_GUARD_SESSION_TOKEN": "local-session-token",
        "SSS_PROJECT_PATH": str(ROOT),
        "SSS_PROTECTED_NETWORK": "local-protected-network",
    }
    completed = subprocess.run(
        [
            docker_executable,
            "compose",
            "-f",
            str(PROTECTED_COMPOSE_FILE),
            "config",
            "--format",
            "json",
        ],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return json.loads(completed.stdout)


def test_protected_agent_has_only_internal_network_and_no_secret() -> None:
    service = _compose_config()["services"]["protected-agent"]

    assert set(service["networks"]) == {"protected"}
    assert service["read_only"] is True
    assert service["cap_drop"] == ["ALL"]
    assert "no-new-privileges:true" in service["security_opt"]
    assert "SSS_APPROVAL_SIGNING_KEY" not in service["environment"]
    assert "SSS_API_BEARER_TOKENS" not in service["environment"]
    assert service["pids_limit"] == 256

    mounts = service["volumes"]
    assert len(mounts) == 1
    assert mounts[0]["type"] == "bind"
    assert mounts[0]["target"] == "/workspace"
    assert all(mount["source"] != "/var/run/docker.sock" for mount in mounts)


def test_network_roles_keep_public_egress_out_of_protected_agent() -> None:
    config = _compose_config()
    services = config["services"]

    assert config["networks"]["protected"]["internal"] is True
    assert set(services["gateway"]["networks"]) == {"gateway-egress", "protected"}
    assert set(services["api"]["networks"]) == {"control-plane", "protected"}
    assert set(services["canary"]["networks"]) == {"protected"}


def test_cli_protected_compose_has_no_administrative_credentials() -> None:
    config = _protected_compose_config()
    service = config["services"]["protected-agent"]

    assert config["networks"]["protected"]["external"] is True
    assert service["read_only"] is True
    assert service["cap_drop"] == ["ALL"]
    assert set(service["environment"]) == {
        "SSS_API_URL",
        "SSS_GATEWAY_URL",
        "SSS_GUARD_SESSION_TOKEN",
    }
    assert "SSS_APPROVAL_SIGNING_KEY" not in service["environment"]
    assert "SSS_API_BEARER_TOKENS" not in service["environment"]
