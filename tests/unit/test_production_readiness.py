from __future__ import annotations

from datetime import UTC, datetime, timedelta

from scripts.production_readiness import worker_is_fresh


def test_worker_freshness_requires_success_within_bound() -> None:
    now = datetime(2026, 9, 14, 12, 0, tzinfo=UTC)

    assert worker_is_fresh("success", now - timedelta(minutes=4), now=now, max_age=300)
    assert not worker_is_fresh("failed", now - timedelta(minutes=1), now=now, max_age=300)
    assert not worker_is_fresh("success", now - timedelta(minutes=6), now=now, max_age=300)
    assert not worker_is_fresh(None, None, now=now, max_age=300)
