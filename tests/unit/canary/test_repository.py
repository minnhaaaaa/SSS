from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from sss_canary.repository import CanaryRepository


def test_repository_records_concurrent_events_without_loss(tmp_path: Path) -> None:
    repository = CanaryRepository(tmp_path / "events.db")
    repository.initialize()

    with ThreadPoolExecutor(max_workers=8) as executor:
        events = list(executor.map(repository.record, ["marker"] * 40))

    assert repository.count() == 40
    assert len({event.event_id for event in events}) == 40
