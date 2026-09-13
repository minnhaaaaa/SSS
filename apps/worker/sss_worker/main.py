"""Executable durable worker entrypoint."""

from __future__ import annotations

import asyncio
import socket
from datetime import UTC, datetime, timedelta
from typing import Any

import typer
from sss_core.config import ExasolSettings

from sss_worker.config import WorkerSettings
from sss_worker.jobs.probe import load_prompt_manifest, run_probe_suite
from sss_worker.providers.openai_compatible import OpenAICompatibleProvider
from sss_worker.repository import ExasolModelObservationSink, WorkerRepository
from sss_worker.scheduler import DurableScheduler, JobHandler, JobOutcome, build_schedule

app = typer.Typer(no_args_is_help=True)


def _components() -> tuple[
    Any,
    WorkerSettings,
    WorkerRepository,
    OpenAICompatibleProvider,
    ExasolModelObservationSink,
]:
    import pyexasol  # type: ignore[import-untyped]

    settings = WorkerSettings.from_env()
    exasol = ExasolSettings.from_env()
    connection = pyexasol.connect(
        dsn=exasol.dsn,
        user=exasol.user,
        password=exasol.password,
        schema=exasol.schema,
        autocommit=False,
    )
    provider = OpenAICompatibleProvider(
        base_url=settings.model_base_url,
        token=settings.read_model_token(),
        model_id=settings.model_id,
        timeout_seconds=settings.request_timeout_seconds,
        max_response_bytes=settings.max_response_bytes,
        retry_attempts=settings.retry_attempts,
    )
    return (
        connection,
        settings,
        WorkerRepository(connection),
        provider,
        ExasolModelObservationSink(connection),
    )


async def _run_probes(
    settings: WorkerSettings,
    provider: OpenAICompatibleProvider,
    sink: ExasolModelObservationSink,
    cursor: str | None,
) -> JobOutcome:
    del cursor
    if settings.prompt_manifest is None or not settings.prompt_manifest.is_file():
        raise ValueError("SSS_PROMPT_MANIFEST must identify a readable JSONL manifest")
    tasks = list(load_prompt_manifest(settings.prompt_manifest))
    await run_probe_suite(provider, tasks, sink, concurrency=settings.concurrency)
    return JobOutcome(
        "success",
        str(settings.prompt_manifest.stat().st_mtime_ns),
        datetime.now(UTC),
    )


def _handlers(
    settings: WorkerSettings,
    provider: OpenAICompatibleProvider,
    sink: ExasolModelObservationSink,
) -> dict[str, JobHandler]:
    return {
        "run_probe_suite": lambda cursor: _run_probes(
            settings, provider, sink, cursor
        ),
    }


async def _run_once(job_name: str) -> bool:
    connection, settings, repository, provider, sink = _components()
    try:
        scheduler = DurableScheduler(
            repository,
            owner=f"{socket.gethostname()}:{id(repository)}",
            handlers=_handlers(settings, provider, sink),
        )
        return await scheduler.run_once(job_name)
    finally:
        connection.close()


async def _run_forever() -> None:
    connection, settings, repository, provider, sink = _components()
    handlers = _handlers(settings, provider, sink)
    scheduler = DurableScheduler(
        repository,
        owner=f"{socket.gethostname()}:{id(repository)}",
        handlers=handlers,
    )
    schedule = build_schedule()
    due = {job_name: datetime.now(UTC) for job_name in handlers}
    try:
        while True:
            now = datetime.now(UTC)
            ready = [job_name for job_name, next_run in due.items() if next_run <= now]
            for job_name in ready:
                try:
                    await scheduler.run_once(job_name)
                finally:
                    due[job_name] = datetime.now(UTC) + schedule[job_name].interval
            next_run = min(due.values())
            delay = max((next_run - datetime.now(UTC)).total_seconds(), 0.1)
            await asyncio.sleep(min(delay, timedelta(minutes=1).total_seconds()))
    finally:
        connection.close()


@app.command("once")
def once(job_name: str) -> None:
    """Run one configured collector job under a durable lease."""
    if not asyncio.run(_run_once(job_name)):
        raise typer.Exit(code=75)


@app.command("run")
def run() -> None:
    """Run configured production collectors at their durable intervals."""
    asyncio.run(_run_forever())


if __name__ == "__main__":
    app()
