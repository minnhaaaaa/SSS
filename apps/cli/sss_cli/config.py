"""Environment-backed CLI and protected-workspace configuration."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from os import environ
from pathlib import Path
from urllib.parse import urlsplit


class CliConfigurationError(ValueError):
    """Raised when CLI runtime configuration is unsafe or incomplete."""


def _http_url(values: Mapping[str, str], key: str, default: str = "") -> str:
    value = values.get(key, default).strip()
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise CliConfigurationError(f"{key} must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password or parsed.fragment:
        raise CliConfigurationError(f"{key} cannot contain credentials or a fragment")
    return value.rstrip("/")


def _optional_http_url(values: Mapping[str, str], key: str) -> str | None:
    if not values.get(key, "").strip():
        return None
    return _http_url(values, key)


def _executable_map(values: Mapping[str, str]) -> Mapping[str, Path]:
    raw = values.get("SSS_REAL_EXECUTABLES_JSON", "{}")
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CliConfigurationError("SSS_REAL_EXECUTABLES_JSON must be valid JSON") from exc
    if not isinstance(decoded, dict):
        raise CliConfigurationError("SSS_REAL_EXECUTABLES_JSON must be a JSON object")
    result: dict[str, Path] = {}
    for name, path_value in decoded.items():
        if not isinstance(name, str) or not isinstance(path_value, str):
            raise CliConfigurationError("executable names and paths must be strings")
        path = Path(path_value)
        if not path.is_absolute():
            raise CliConfigurationError(f"real executable for {name!r} must be absolute")
        result[name.casefold()] = path
    return result


@dataclass(frozen=True, slots=True)
class CliSettings:
    api_url: str
    gateway_url: str
    protected_api_url: str | None
    protected_gateway_url: str | None
    api_token: str | None
    real_executables: Mapping[str, Path]
    allowed_environment_keys: frozenset[str]
    docker_executable: str
    protected_compose_file: Path
    protected_service: str
    agent_image: str | None
    protected_network: str | None
    project_path: Path | None
    guard_session_token: str | None
    npm_registry_url: str = "https://registry.npmjs.org"
    project_id: str = "project-demo"
    agent_family: str = "codex"
    demo_artifact_sha256: str = "b" * 64

    @classmethod
    def from_env(cls, values: Mapping[str, str] | None = None) -> CliSettings:
        source = environ if values is None else values
        allowed = frozenset(
            key.strip()
            for key in source.get(
                "SSS_ALLOWED_ENV_KEYS",
                "PATH,LANG,LC_ALL,TERM,CI,SYSTEMROOT,WINDIR,COMSPEC,PATHEXT,TEMP,TMP",
            ).split(",")
            if key.strip()
        )
        compose_file = Path(
            source.get("SSS_PROTECTED_COMPOSE_FILE", "infra/docker/compose.protected.yaml")
        )
        service = source.get("SSS_PROTECTED_SERVICE", "protected-agent").strip()
        if not service:
            raise CliConfigurationError("SSS_PROTECTED_SERVICE cannot be empty")
        docker_executable = source.get("SSS_DOCKER_EXECUTABLE", "docker").strip()
        if not docker_executable:
            raise CliConfigurationError("SSS_DOCKER_EXECUTABLE cannot be empty")
        artifact_sha256 = source.get("SSS_DEMO_ARTIFACT_SHA256", "b" * 64)
        if len(artifact_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in artifact_sha256
        ):
            raise CliConfigurationError("SSS_DEMO_ARTIFACT_SHA256 must be a lowercase SHA-256")
        project_id = source.get("SSS_PROJECT_ID", "project-demo").strip()
        agent_family = source.get("SSS_AGENT_FAMILY", "codex").strip()
        if not project_id or not agent_family:
            raise CliConfigurationError("SSS_PROJECT_ID and SSS_AGENT_FAMILY are required")
        return cls(
            api_url=_http_url(source, "SSS_API_URL"),
            gateway_url=_http_url(source, "SSS_GATEWAY_URL"),
            protected_api_url=_optional_http_url(source, "SSS_PROTECTED_API_URL"),
            protected_gateway_url=_optional_http_url(source, "SSS_PROTECTED_GATEWAY_URL"),
            api_token=source.get("SSS_API_TOKEN") or None,
            real_executables=_executable_map(source),
            allowed_environment_keys=allowed,
            docker_executable=docker_executable,
            protected_compose_file=compose_file,
            protected_service=service,
            agent_image=source.get("SSS_AGENT_IMAGE") or None,
            protected_network=source.get("SSS_PROTECTED_NETWORK") or None,
            project_path=(
                Path(source["SSS_PROJECT_PATH"]).expanduser()
                if source.get("SSS_PROJECT_PATH")
                else None
            ),
            guard_session_token=source.get("SSS_GUARD_SESSION_TOKEN") or None,
            npm_registry_url=_http_url(
                source,
                "SSS_NPM_REGISTRY_URL",
                "https://registry.npmjs.org",
            ),
            project_id=project_id,
            agent_family=agent_family,
            demo_artifact_sha256=artifact_sha256,
        )
