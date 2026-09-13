"""Executable package-manager shim entrypoint."""

from __future__ import annotations

import sys
from os import environ
from pathlib import Path

from sss_cli.adapters import HttpGuardClient
from sss_cli.config import CliSettings
from sss_cli.guard import GuardRunner
from sss_cli.manager_environment import build_manager_environment
from sss_cli.process import SafeProcessRunner


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments:
        print("SSS BLOCK — package manager name is required")
        return 23
    manager, *manager_arguments = arguments
    settings = CliSettings.from_env()
    if settings.api_token is None:
        print("SSS BLOCK — API token is not configured")
        return 23
    runner = GuardRunner(
        client=HttpGuardClient(
            api_url=settings.api_url,
            token=settings.api_token,
            approval_token=settings.approval_token,
            approval_nonce=settings.approval_nonce,
        ),
        process_runner=SafeProcessRunner(executables=settings.real_executables),
        registry_origin=settings.npm_registry_url,
        project_id=settings.project_id,
        agent_family=settings.agent_family,
        artifact_sha256=settings.demo_artifact_sha256,
        cwd=Path.cwd().resolve(),
        environment=build_manager_environment(settings, environ),
        write=print,
        pypi_registry_origin=settings.pypi_registry_url,
    )
    return runner.run(manager, manager_arguments)


if __name__ == "__main__":
    raise SystemExit(main())
