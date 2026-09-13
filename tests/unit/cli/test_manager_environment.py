from __future__ import annotations

from pathlib import Path

from sss_cli.config import CliSettings
from sss_cli.manager_environment import build_manager_environment


def test_real_manager_receives_gateway_routes_without_guard_credentials() -> None:
    settings = CliSettings(
        api_url="http://api:8000",
        gateway_url="http://gateway:8080",
        protected_api_url=None,
        protected_gateway_url=None,
        api_token="guard-token",
        real_executables={"npm": Path("/usr/bin/npm")},
        allowed_environment_keys=frozenset({"PATH", "LANG"}),
        docker_executable="docker",
        protected_compose_file=Path("compose.yaml"),
        protected_service="agent",
        agent_image=None,
        protected_network=None,
        project_path=None,
        guard_session_token=None,
    )

    environment = build_manager_environment(
        settings,
        {
            "PATH": "/safe/bin",
            "LANG": "C.UTF-8",
            "SSS_API_TOKEN": "must-not-reach-manager",
            "SSS_APPROVAL_TOKEN": "must-not-reach-manager",
        },
    )

    assert environment == {
        "PATH": "/safe/bin",
        "LANG": "C.UTF-8",
        "NPM_CONFIG_REGISTRY": "http://gateway:8080/v1/registry/npm",
        "YARN_NPM_REGISTRY_SERVER": "http://gateway:8080/v1/registry/npm",
        "PIP_INDEX_URL": "http://gateway:8080/v1/registry/pypi/simple",
        "UV_INDEX_URL": "http://gateway:8080/v1/registry/pypi/simple",
    }
