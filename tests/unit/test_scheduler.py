from __future__ import annotations

from datetime import timedelta

from sss_worker.scheduler import build_schedule


def test_required_worker_cadences_are_explicit() -> None:
    schedule = build_schedule()

    assert schedule["recheck_high_risk"].interval == timedelta(minutes=15)
    assert schedule["recheck_watchlist"].interval == timedelta(hours=6)
    assert schedule["run_probe_suite"].interval == timedelta(days=1)
    assert schedule["scan_public_sources"].interval == timedelta(hours=1)
    assert schedule["refresh_pypi_baseline"].interval == timedelta(days=1)
    assert all(job.coalesce and job.max_instances == 1 for job in schedule.values())
