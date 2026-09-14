from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).parents[2]


def _free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _wait_ready(base_url: str) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            if httpx.get(f"{base_url}/health/live", timeout=0.5).status_code == 200:
                return
        except httpx.HTTPError:
            time.sleep(0.05)
    raise AssertionError("Guard API did not become ready")


def test_real_agent_is_blocked_before_pnpm_starts(tmp_path: Path) -> None:
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    token = "e2e-guard-token"  # noqa: S105 - explicit non-secret test credential.
    pnpm_path = shutil.which("pnpm")
    assert pnpm_path is not None
    environment = {
        **os.environ,
        "SSS_ENV": "test",
        "SSS_API_BEARER_TOKENS": token,
        "SSS_API_TOKEN": token,
        "SSS_API_URL": base_url,
        "SSS_GATEWAY_URL": "http://127.0.0.1:9",
        "SSS_NPM_REGISTRY_URL": "https://npm.demo.sss.test",
        "SSS_PROJECT_ID": "project-demo",
        "SSS_AGENT_FAMILY": "codex",
        "SSS_DEMO_ARTIFACT_SHA256": "b" * 64,
        "SSS_REAL_EXECUTABLES_JSON": json.dumps(
            {"pnpm": str(Path(pnpm_path).resolve())}
        ),
    }
    api = subprocess.Popen(
        [
            str(ROOT / ".venv/bin/uvicorn"),
            "--factory",
            "sss_api.main:create_app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        _wait_ready(base_url)
        agent_environment = {
            **environment,
            "PATH": (
                f"{ROOT / 'apps/cli/sss_cli/shims'}:"
                f"{ROOT / '.venv/bin'}:{environment['PATH']}"
            ),
        }
        completed = subprocess.run(
            [str(ROOT / ".venv/bin/sss-demo-agent")],
            cwd=tmp_path,
            env=agent_environment,
            capture_output=True,
            text=True,
            check=False,
        )
        headers = {"Authorization": f"Bearer {token}"}
        interventions = httpx.get(
            f"{base_url}/v1/interventions", headers=headers
        ).json()["items"]
        attempts = httpx.get(
            f"{base_url}/v1/install-attempts", headers=headers
        ).json()["items"]
        operator = subprocess.run(
            [str(ROOT / ".venv/bin/sss"), "intervene"],
            cwd=tmp_path,
            env=environment,
            input="k\n",
            capture_output=True,
            text=True,
            check=False,
        )
        pending_after = httpx.get(
            f"{base_url}/v1/interventions", headers=headers
        ).json()["items"]
    finally:
        api.terminate()
        api.wait(timeout=5)

    assert completed.returncode == 23
    assert "SSS BLOCK" in completed.stdout
    assert "Absence confidence: 100" in completed.stdout
    assert "Target attractiveness: 95" in completed.stdout
    assert "Package policy risk: 75" in completed.stdout
    assert "Installation was not started." in completed.stdout
    assert len(interventions) == 1
    assert len(attempts) == 1
    assert attempts[0]["child_started"] is False
    assert operator.returncode == 0
    assert "SSS operator intervention required" in operator.stdout
    assert "Installation remains blocked." in operator.stdout
    assert pending_after == []
    assert not (tmp_path / "node_modules").exists()
