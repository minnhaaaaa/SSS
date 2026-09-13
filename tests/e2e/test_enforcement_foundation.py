from __future__ import annotations

import json
import os
import secrets
import shutil
import socket
import subprocess
import time
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = ROOT / "infra" / "docker" / "compose.enforcement.yaml"


def _run(
    compose: list[str],
    environment: dict[str, str],
    *arguments: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*compose, *arguments],
        cwd=ROOT,
        env=environment,
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _free_port() -> str:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return str(listener.getsockname()[1])


def _local_python_digest(docker_executable: str) -> str:
    completed = subprocess.run(
        [
            docker_executable,
            "image",
            "inspect",
            "python:3.12-slim",
            "--format",
            "{{index .RepoDigests 0}}",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    digest = completed.stdout.strip()
    if completed.returncode or not digest:
        pytest.skip("a local python:3.12-slim image with a repository digest is required")
    return digest


def _wait_for_healthy(
    compose: list[str], environment: dict[str, str], services: tuple[str, ...]
) -> None:
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        completed = _run(compose, environment, "ps", "--format", "json", check=False)
        if completed.returncode == 0:
            rows = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
            health = {row["Service"]: row.get("Health") for row in rows}
            if all(health.get(service) == "healthy" for service in services):
                return
        time.sleep(0.25)
    raise AssertionError(f"services did not become healthy: {services}")


@pytest.mark.docker
def test_live_compose_security_and_local_canary() -> None:
    if os.environ.get("SSS_RUN_DOCKER_TESTS") != "true":
        pytest.skip("set SSS_RUN_DOCKER_TESTS=true to run live Docker tests")
    docker_executable = shutil.which("docker")
    if docker_executable is None:
        pytest.skip("Docker CLI is unavailable")

    project_name = f"sss-foundation-{os.getpid()}"
    compose = [
        docker_executable,
        "compose",
        "-p",
        project_name,
        "-f",
        str(COMPOSE_FILE),
    ]
    api_token = secrets.token_urlsafe(24)
    canary_token = secrets.token_urlsafe(24)
    marker = secrets.token_urlsafe(16)
    base_image = _local_python_digest(docker_executable)
    environment = {
        **os.environ,
        "SSS_PYTHON_BASE_IMAGE": base_image,
        "SSS_UV_VERSION": "0.12.13",
        "SSS_AGENT_BASE_IMAGE": base_image,
        "SSS_API_BEARER_TOKENS": api_token,
        "SSS_GATEWAY_UPSTREAMS_JSON": '{"pypi":"https://pypi.org"}',
        "SSS_CANARY_TOKEN": canary_token,
        "SSS_CANARY_MARKER": marker,
        "SSS_PROJECT_PATH": str(ROOT),
        "SSS_PROTECTED_NETWORK": f"{project_name}-protected",
        "SSS_API_HOST_PORT": _free_port(),
        "SSS_GATEWAY_HOST_PORT": _free_port(),
        "SSS_API_MAX_BODY_BYTES": "64",
    }

    try:
        _run(compose, environment, "up", "-d", "--build", "api", "gateway", "canary")
        _wait_for_healthy(compose, environment, ("api", "gateway", "canary"))

        api_base = f"http://127.0.0.1:{environment['SSS_API_HOST_PORT']}"
        gateway_base = f"http://127.0.0.1:{environment['SSS_GATEWAY_HOST_PORT']}"
        api_health = httpx.get(f"{api_base}/health/live", timeout=3)
        gateway_health = httpx.get(f"{gateway_base}/health/live", timeout=3)
        unauthenticated = httpx.get(f"{api_base}/v1/events", timeout=3)
        oversized = httpx.post(f"{api_base}/missing", content=b"x" * 65, timeout=3)
        assert api_health.status_code == 200
        assert api_health.headers["X-Request-ID"]
        assert gateway_health.status_code == 200
        assert unauthenticated.status_code == 401
        assert oversized.status_code == 413

        internal = _run(
            compose,
            environment,
            "run",
            "--rm",
            "--no-deps",
            "protected-agent",
            "python",
            "-c",
            (
                "import urllib.request; "
                "response = urllib.request.urlopen('http://api:8000/health/live', timeout=3); "
                "assert response.status == 200"
            ),
        )
        assert internal.returncode == 0

        boundary_script = """
import os
import pathlib
import socket

assert os.getuid() != 0
assert not pathlib.Path('/var/run/docker.sock').exists()
try:
    pathlib.Path('/must-not-write').write_text('blocked')
except OSError:
    pass
else:
    raise AssertionError('root filesystem is writable')
try:
    socket.create_connection(('pypi.org', 443), timeout=3)
except OSError:
    pass
else:
    raise AssertionError('protected container has public egress')
"""
        boundary = _run(
            compose,
            environment,
            "run",
            "--rm",
            "--no-deps",
            "protected-agent",
            "python",
            "-c",
            boundary_script,
        )
        assert boundary.returncode == 0

        canary_script = f"""
import json
import urllib.request

headers = {{'Authorization': 'Bearer {canary_token}', 'Content-Type': 'application/json'}}
base = 'http://canary:8090'
urllib.request.urlopen(urllib.request.Request(base + '/v1/reset', headers=headers, method='POST'))
body = json.dumps({{'marker': '{marker}'}}).encode()
urllib.request.urlopen(
    urllib.request.Request(base + '/v1/events', data=body, headers=headers, method='POST')
)
result = json.loads(
    urllib.request.urlopen(urllib.request.Request(base + '/v1/count', headers=headers)).read()
)
assert result == {{'count': 1}}
"""
        canary = _run(compose, environment, "exec", "-T", "api", "python", "-c", canary_script)
        assert canary.returncode == 0

        _run(compose, environment, "restart", "canary")
        _wait_for_healthy(compose, environment, ("api", "gateway", "canary"))
        persisted_count_script = f"""
import json
import urllib.request

headers = {{'Authorization': 'Bearer {canary_token}'}}
request = urllib.request.Request('http://canary:8090/v1/count', headers=headers)
assert json.loads(urllib.request.urlopen(request).read()) == {{'count': 1}}
"""
        persisted = _run(
            compose,
            environment,
            "exec",
            "-T",
            "api",
            "python",
            "-c",
            persisted_count_script,
        )
        assert persisted.returncode == 0

        gateway_script = """
import httpx
import time

errors = []
response = None
with httpx.Client(timeout=15, follow_redirects=False, trust_env=False) as client:
    for _attempt in range(3):
        try:
            response = client.get('https://pypi.org/simple/pip/')
            break
        except httpx.HTTPError as exc:
            errors.append(str(exc))
            time.sleep(1)
assert response is not None, errors
assert response.status_code == 200
"""
        gateway = _run(
            compose,
            environment,
            "exec",
            "-T",
            "gateway",
            "python",
            "-c",
            gateway_script,
        )
        assert gateway.returncode == 0
    finally:
        _run(compose, environment, "down", "--volumes", "--remove-orphans", check=False)
