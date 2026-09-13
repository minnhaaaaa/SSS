from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sss_worker.scheduler import DurableScheduler, JobOutcome


class MemoryWorkerRepository:
    def __init__(self) -> None:
        self.owner: str | None = None
        self.expires: datetime | None = None
        self.saved_cursor: str | None = "before"
        self.outcome: str | None = None

    def acquire_lease(self, job: str, owner: str, *, now: datetime, ttl: timedelta) -> bool:
        del job
        if self.owner is not None and self.expires is not None and self.expires > now:
            return False
        self.owner, self.expires = owner, now + ttl
        return True

    def cursor(self, job: str, source: str) -> str | None:
        del job, source
        return self.saved_cursor

    def finish(
        self,
        job: str,
        source: str,
        *,
        outcome: str,
        cursor: str | None,
        data_as_of: datetime,
    ) -> None:
        del job, source, data_as_of
        self.outcome = outcome
        if outcome == "success":
            self.saved_cursor = cursor

    def release(self, job: str, owner: str) -> None:
        del job
        if self.owner == owner:
            self.owner = None

    def heartbeat(
        self, job: str, owner: str, *, now: datetime, ttl: timedelta
    ) -> bool:
        del job
        if self.owner != owner:
            return False
        self.expires = now + ttl
        return True


@pytest.mark.asyncio
async def test_success_advances_cursor_and_failure_preserves_it() -> None:
    repository = MemoryWorkerRepository()

    async def success(cursor: str | None) -> JobOutcome:
        assert cursor == "before"
        return JobOutcome("success", "after", datetime.now(UTC))

    scheduler = DurableScheduler(  # type: ignore[arg-type]
        repository, owner="worker-1", handlers={"run_probe_suite": success}
    )
    assert await scheduler.run_once("run_probe_suite") is True
    assert repository.saved_cursor == "after"

    async def failed(cursor: str | None) -> JobOutcome:
        assert cursor == "after"
        return JobOutcome("rate_limited", "must-not-save", datetime.now(UTC))

    scheduler = DurableScheduler(  # type: ignore[arg-type]
        repository, owner="worker-1", handlers={"run_probe_suite": failed}
    )
    assert await scheduler.run_once("run_probe_suite") is False
    assert repository.saved_cursor == "after"


@pytest.mark.asyncio
async def test_concurrent_worker_is_rejected_and_expired_lease_reclaimed() -> None:
    repository = MemoryWorkerRepository()
    now = datetime.now(UTC)
    assert repository.acquire_lease(
        "run_probe_suite", "worker-1", now=now, ttl=timedelta(seconds=1)
    )
    assert not repository.acquire_lease(
        "run_probe_suite", "worker-2", now=now, ttl=timedelta(seconds=1)
    )
    assert repository.acquire_lease(
        "run_probe_suite",
        "worker-2",
        now=now + timedelta(seconds=2),
        ttl=timedelta(seconds=1),
    )
