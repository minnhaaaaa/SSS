"""CLI entrypoint for independently available operational commands."""

from __future__ import annotations

from os import environ
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from sss_cli.adapters import HttpGuardClient
from sss_cli.config import CliSettings, OperatorSettings
from sss_cli.doctor import check_http_service
from sss_cli.guard import GuardRunner
from sss_cli.intervene import HttpInterventionClient, run_intervention
from sss_cli.manager_environment import build_manager_environment
from sss_cli.process import SafeProcessRunner
from sss_cli.protect import ProtectedLauncher
from sss_cli.protected_config import build_protected_compose_environment

app = typer.Typer(no_args_is_help=True)
console = Console()


def _guard_runner(settings: CliSettings) -> GuardRunner:
    if settings.api_token is None:
        console.print("SSS_API_TOKEN is required for Guard assessment.")
        raise typer.Exit(code=2)
    return GuardRunner(
        client=HttpGuardClient(
            api_url=settings.api_url,
            token=settings.api_token,
            approval_token=settings.approval_token,
            approval_nonce=settings.approval_nonce,
        ),
        process_runner=SafeProcessRunner(executables=settings.real_executables),
        registry_origin=settings.npm_registry_url,
        pypi_registry_origin=settings.pypi_registry_url,
        project_id=settings.project_id,
        agent_family=settings.agent_family,
        artifact_sha256=settings.demo_artifact_sha256,
        cwd=Path.cwd().resolve(),
        environment=build_manager_environment(settings, environ),
        write=console.print,
    )


@app.command()
def doctor() -> None:
    """Check the independently available API and gateway processes."""
    settings = CliSettings.from_env()
    checks = (
        check_http_service(
            "api",
            settings.api_url,
            path="/health/ready",
            expected_status="ready",
        ),
        check_http_service("gateway", settings.gateway_url),
    )
    table = Table("Service", "Healthy", "Detail")
    for check in checks:
        table.add_row(check.name, "yes" if check.healthy else "no", check.detail)
    console.print(table)
    if not all(check.healthy for check in checks):
        raise typer.Exit(code=1)


@app.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def protect(context: typer.Context) -> None:
    """Launch an argument-vector command in the configured protected service."""
    settings = CliSettings.from_env()
    compose_environment = build_protected_compose_environment(settings, environ)
    launcher = ProtectedLauncher(
        docker_executable=settings.docker_executable,
        compose_file=settings.protected_compose_file.resolve(),
        service=settings.protected_service,
    )
    raise typer.Exit(code=launcher.launch(context.args, environment=compose_environment))


@app.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def guard(
    context: typer.Context,
    manager: str = typer.Argument(help="Package manager executable name."),
) -> None:
    """Assess an install and run the real manager only when policy allows it."""

    raise typer.Exit(code=_guard_runner(CliSettings.from_env()).run(manager, context.args))


@app.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def check(
    context: typer.Context,
    manager: str = typer.Argument(help="Package manager executable name."),
) -> None:
    """Assess an install vector without starting a package manager."""

    raise typer.Exit(code=_guard_runner(CliSettings.from_env()).check_only(manager, context.args))


@app.command()
def intervene(
    watch: bool = typer.Option(False, "--watch", help="Continue watching for interventions."),
) -> None:
    """Review blocked agent installs from a separate operator terminal."""
    settings = OperatorSettings.from_env()
    if settings.api_token is None:
        console.print("SSS_API_TOKEN is required for operator intervention.")
        raise typer.Exit(code=2)
    client = HttpInterventionClient(api_url=settings.api_url, token=settings.api_token)
    run_intervention(
        client,
        input_line=typer.prompt,
        write=console.print,
        once=not watch,
    )


if __name__ == "__main__":
    app()
