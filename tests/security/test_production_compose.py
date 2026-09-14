from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "infra/docker/production.compose.yaml"


def _config(tmp_path: Path) -> dict[str, Any]:
    docker = shutil.which("docker")
    if docker is None:
        pytest.skip("Docker CLI is unavailable")
    secret_names = (
        "exasol_password",
        "approval_signing_key",
        "api_credentials",
        "browser_api_token",
        "operator_password_hash",
        "tls_certificate",
        "tls_private_key",
        "model_provider_token",
        "agent_api_token",
    )
    environment = {
        **os.environ,
        "SSS_PYTHON_BASE_IMAGE": "python-image@sha256:test",
        "SSS_NODE_BASE_IMAGE": "node-image@sha256:test",
        "SSS_CADDY_IMAGE": "caddy-image@sha256:test",
        "SSS_UV_VERSION": "0.12.13",
        "SSS_EXASOL_DSN": "db.internal.example:8563",
        "SSS_EXASOL_USER": "sss_service",
        "SSS_EXASOL_SCHEMA": "SSS",
        "SSS_GATEWAY_UPSTREAMS_JSON": '{"npm":"https://registry.npmjs.org"}',
        "SSS_GATEWAY_PERMITS_JSON": '{"npm":{"/safe-lib":null}}',
        "SSS_MODEL_BASE_URL": "https://models.example/v1",
        "SSS_MODEL_ID": "approved-model",
        "SSS_PROMPT_MANIFEST": "/run/config/prompts.json",
        "SSS_TLS_HOST": "sss.example.test",
        "SSS_OPERATOR_USERNAME": "operator",
        "SSS_PROJECT_PATH": str(ROOT),
        "SSS_PROJECT_ID": "project-production-test",
        "SSS_ARTIFACT_SHA256": "a" * 64,
    }
    prompt_manifest = tmp_path / "prompts.jsonl"
    prompt_manifest.write_text('{"id":"test","prompt":"test"}\n', encoding="utf-8")
    environment["SSS_PROMPT_MANIFEST_FILE"] = str(prompt_manifest)
    for name in secret_names:
        path = tmp_path / name
        path.write_text(f"test-{name}\n", encoding="utf-8")
        environment[f"SSS_{name.upper()}_FILE"] = str(path)
    completed = subprocess.run(
        [
            docker,
            "compose",
            "-f",
            str(COMPOSE),
            "--profile",
            "agent",
            "config",
            "--format",
            "json",
        ],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_production_exposes_only_tls_proxy_and_external_exasol(tmp_path: Path) -> None:
    config = _config(tmp_path)
    services = config["services"]

    assert {name for name, service in services.items() if service.get("ports")} == {"proxy"}
    assert services["proxy"]["ports"][0]["published"] == "8443"
    assert services["api"]["environment"]["SSS_ENV"] == "production"
    assert services["api"]["environment"]["SSS_EXASOL_REQUIRED"] == "true"
    assert "SSS_EXASOL_PASSWORD" not in services["api"]["environment"]
    assert "SSS_APPROVAL_SIGNING_KEY" not in services["api"]["environment"]
    assert "exasol" not in services
    assert not {"demo", "canary", "registry", "registry-seed"} & set(services)


def test_production_services_have_hardened_boundaries(tmp_path: Path) -> None:
    config = _config(tmp_path)
    services = config["services"]

    for name in ("api", "worker", "gateway", "web", "proxy", "protected-agent"):
        service = services[name]
        assert service["read_only"] is True
        assert service["cap_drop"] == ["ALL"]
        assert "no-new-privileges:true" in service["security_opt"]
        assert service["restart"] == "unless-stopped"
        assert service["pids_limit"] > 0
        assert service["logging"]["driver"] == "json-file"

    agent = services["protected-agent"]
    assert set(agent["networks"]) == {"protected"}
    assert config["networks"]["protected"]["internal"] is True
    assert "/var/run/docker.sock" not in json.dumps(agent)
    assert "SSS_APPROVAL_SIGNING_KEY" not in json.dumps(agent)
    assert set(services["gateway"]["networks"]) == {"gateway-egress", "protected"}
    assert set(services["api"]["networks"]) == {"app", "protected", "control-egress"}
    assert set(services["worker"]["networks"]) == {"app", "control-egress"}
    assert config["networks"]["app"]["internal"] is True
    assert config["networks"]["control-egress"].get("internal") is not True


def test_caddy_removes_forged_identity_and_injects_scoped_token() -> None:
    caddyfile = (ROOT / "infra/docker/Caddyfile.production").read_text(encoding="utf-8")

    assert "header_up -X-SSS-Operator" in caddyfile
    assert "header_up -X-SSS-Proxy-Token" in caddyfile
    assert "browser_api_token" in caddyfile
    assert "basic_auth" in caddyfile
    assert "tls /run/secrets/tls_certificate /run/secrets/tls_private_key" in caddyfile
