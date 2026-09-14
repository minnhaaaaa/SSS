"""CLI entrypoint for independently available operational commands."""

from __future__ import annotations

import json
from os import environ
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from sss_cli.admin import generate_token
from sss_cli.config import CliSettings, OperatorSettings
from sss_cli.config_file import StoredCliConfig, default_config_path, write_config
from sss_cli.doctor import check_http_service
from sss_cli.intervene import HttpInterventionClient, run_intervention
from sss_cli.protect import ProtectedLauncher
from sss_cli.protected_config import build_protected_compose_environment

app = typer.Typer(no_args_is_help=True)
admin_app = typer.Typer(no_args_is_help=True)
token_app = typer.Typer(no_args_is_help=True)
app.add_typer(admin_app, name="admin")
admin_app.add_typer(token_app, name="token")
console = Console()


def _write_operator_line(message: str, *, output: Console = console) -> None:
    """Emit copyable approval credentials without terminal-width wrapping."""
    output.print(message, soft_wrap=True)


@app.command()
def configure(
    server: Annotated[str, typer.Option("--server", help="Guard API base URL.")],
    token_file: Annotated[
        str, typer.Option("--token-file", help="Path to a mode-0600 token file.")
    ],
    organization_id: Annotated[
        str, typer.Option("--organization", help="Organization identifier.")
    ] = "default",
    project_id: Annotated[
        str, typer.Option("--project", help="Protected project identifier.")
    ] = "default",
) -> None:
    """Write safe local configuration without copying the raw token."""
    config = StoredCliConfig(server, Path(token_file), organization_id, project_id)
    destination = default_config_path(environ)
    write_config(config, destination)
    console.print(f"Wrote SSS configuration to {destination}")


@token_app.command("generate")
def generate_admin_token(
    credential_id: Annotated[str, typer.Argument(help="Stable credential identifier.")],
    scope: Annotated[
        list[str], typer.Option("--scope", help="Repeat for every granted scope.")
    ],
) -> None:
    """Generate a raw token once and its safe digest-backed credential record."""
    generated = generate_token(credential_id, frozenset(scope))
    console.print(f"Raw token (shown once): {generated.raw_token}")
    console.print(json.dumps(generated.record.to_json(), sort_keys=True))


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
        write=_write_operator_line,
        once=not watch,
    )


if __name__ == "__main__":
    app()
