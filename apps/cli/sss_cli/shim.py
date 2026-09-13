"""Executable package-manager shim entrypoint."""

from __future__ import annotations

import sys
from collections.abc import Callable
from os import environ
from pathlib import Path

from sss_cli.adapters import HttpGuardClient
from sss_cli.config import CliConfigurationError, CliSettings
from sss_cli.config_file import default_config_path, load_config
from sss_cli.guard import GuardClient, GuardRunner, ManagerRunner
from sss_cli.process import SafeProcessRunner


def run_shim(
    client_name: str,
    argv: list[str],
    environment: dict[str, str] | None = None,
    *,
    guard_client: GuardClient | None = None,
    process_runner: ManagerRunner | None = None,
    write: Callable[[str], None] = print,
) -> int:
    values = dict(environ if environment is None else environment)
    try:
        if not values.get("SSS_API_TOKEN"):
            config_path = Path(
                values.get("SSS_CONFIG_FILE", str(default_config_path(values)))
            )
            if config_path.is_file():
                config = load_config(config_path)
                values["SSS_API_URL"] = config.server
                values.setdefault("SSS_GATEWAY_URL", config.server)
                values["SSS_API_TOKEN"] = config.read_token()
                values["SSS_PROJECT_ID"] = config.project_id
        settings = CliSettings.from_env(values)
    except CliConfigurationError as exc:
        write(f"SSS BLOCK — {exc}")
        write("Installation was not started.")
        return 23
    if settings.api_token is None:
        write("SSS BLOCK — API token is not configured")
        return 23
    runner = GuardRunner(
        client=guard_client
        or HttpGuardClient(api_url=settings.api_url, token=settings.api_token),
        process_runner=process_runner
        or SafeProcessRunner(executables=settings.real_executables),
        registry_origin=settings.npm_registry_url,
        pypi_registry_origin=settings.pypi_registry_url,
        project_id=settings.project_id,
        agent_family=settings.agent_family,
        artifact_sha256=settings.demo_artifact_sha256,
        cwd=Path.cwd().resolve(),
        environment=values,
        write=write,
    )
    return runner.run(client_name, argv)


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments:
        print("SSS BLOCK — package manager name is required")
        return 23
    manager, *manager_arguments = arguments
    return run_shim(manager, manager_arguments)


def main_for_executable() -> None:
    raise SystemExit(run_shim(Path(sys.argv[0]).name, list(sys.argv[1:])))


if __name__ == "__main__":
    raise SystemExit(main())
