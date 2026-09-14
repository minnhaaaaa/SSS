from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol


class WorkerState(Protocol):
    def acquire_lease(
        self, job_name: str, owner: str, *, now: datetime, ttl: timedelta
    ) -> bool: ...
    def heartbeat(
        self, job_name: str, owner: str, *, now: datetime, ttl: timedelta
    ) -> bool: ...
    def release(self, job_name: str, owner: str) -> None: ...
    def cursor(self, job_name: str, source_id: str) -> str | None: ...
    def finish(
        self,
        job_name: str,
        source_id: str,
        *,
        outcome: str,
        cursor: str | None,
        data_as_of: datetime,
    ) -> None: ...


@dataclass(frozen=True)
class ScheduledJob:
    interval: timedelta
    coalesce: bool = True
    max_instances: int = 1


def build_schedule() -> dict[str, ScheduledJob]:
    return {
        "recheck_high_risk": ScheduledJob(timedelta(minutes=15)),
        "recheck_watchlist": ScheduledJob(timedelta(hours=6)),
        "run_probe_suite": ScheduledJob(timedelta(days=1)),
        "scan_public_sources": ScheduledJob(timedelta(hours=1)),
        "refresh_pypi_baseline": ScheduledJob(timedelta(days=1)),
    }


@dataclass(frozen=True, slots=True)
class JobOutcome:
    outcome: str
    cursor: str | None
    data_as_of: datetime


JobHandler = Callable[[str | None], Awaitable[JobOutcome]]


class DurableScheduler:
    def __init__(
        self,
        repository: WorkerState,
        *,
        owner: str,
        handlers: dict[str, JobHandler],
        lease_ttl: timedelta = timedelta(minutes=10),
    ) -> None:
        self._repository = repository
        self._owner = owner
        self._handlers = handlers
        self._lease_ttl = lease_ttl

    async def run_once(self, job_name: str, *, source_id: str = "default") -> bool:
        if job_name not in build_schedule() or job_name not in self._handlers:
            raise ValueError(f"unsupported or unconfigured worker job: {job_name}")
        now = datetime.now(UTC)
        if not self._repository.acquire_lease(
            job_name, self._owner, now=now, ttl=self._lease_ttl
        ):
            return False
        heartbeat = asyncio.create_task(self._heartbeat(job_name))
        try:
            cursor = self._repository.cursor(job_name, source_id)
            try:
                result = await self._handlers[job_name](cursor)
            except Exception:
                self._repository.finish(
                    job_name,
                    source_id,
                    outcome="failed",
                    cursor=cursor,
                    data_as_of=datetime.now(UTC),
                )
                raise
            self._repository.finish(
                job_name,
                source_id,
                outcome=result.outcome,
                cursor=result.cursor,
                data_as_of=result.data_as_of,
            )
            return result.outcome == "success"
        finally:
            heartbeat.cancel()
            try:
                with suppress(asyncio.CancelledError):
                    await heartbeat
            finally:
                self._repository.release(job_name, self._owner)

    async def _heartbeat(self, job_name: str) -> None:
        interval = max(self._lease_ttl.total_seconds() / 3, 0.05)
        while True:
            await asyncio.sleep(interval)
            if not self._repository.heartbeat(
                job_name,
                self._owner,
                now=datetime.now(UTC),
                ttl=self._lease_ttl,
            ):
                raise RuntimeError(f"lost worker lease for {job_name}")
