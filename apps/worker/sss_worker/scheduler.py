from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta


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
