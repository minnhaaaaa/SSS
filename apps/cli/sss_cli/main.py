"""CLI entrypoint for independently available operational commands."""

from __future__ import annotations

from os import environ

import typer
from rich.console import Console
from rich.table import Table

from sss_cli.config import CliSettings
from sss_cli.doctor import check_http_service
from sss_cli.protect import ProtectedLauncher
from sss_cli.protected_config import build_protected_compose_environment

app = typer.Typer(no_args_is_help=True)
console = Console()


@app.command()
def doctor() -> None:
    """Check the independently available API and gateway processes."""
    settings = CliSettings.from_env()
    checks = (
        check_http_service("api", settings.api_url),
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


if __name__ == "__main__":
    app()
