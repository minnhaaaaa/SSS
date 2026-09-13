from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts import replay_exasol

ROOT = Path(__file__).parents[2]


def test_replay_fixture_can_reset_before_loading(monkeypatch: Any) -> None:
    calls: list[str] = []

    class RecordingRepository:
        def __init__(self, connection: object) -> None:
            assert connection is sentinel

        def reset(self, fixture: object) -> None:
            calls.append("reset")

        def replay_global_evidence(self, fixture: object) -> None:
            calls.append("replay")

    sentinel = object()
    monkeypatch.setattr(replay_exasol, "ExasolDemoRepository", RecordingRepository)

    fixture = replay_exasol.replay_fixture(
        sentinel,
        ROOT / "demo/fixtures/fixed-intelligence.json",
        reset=True,
    )

    assert calls == ["reset", "replay"]
    assert fixture.verified_model_recommendations == 46


def test_replay_fixture_preserves_other_demo_stages_by_default(monkeypatch: Any) -> None:
    calls: list[str] = []

    class RecordingRepository:
        def __init__(self, connection: object) -> None:
            return None

        def reset(self, fixture: object) -> None:
            calls.append("reset")

        def replay_global_evidence(self, fixture: object) -> None:
            calls.append("replay")

    monkeypatch.setattr(replay_exasol, "ExasolDemoRepository", RecordingRepository)

    replay_exasol.replay_fixture(
        object(),
        ROOT / "demo/fixtures/fixed-intelligence.json",
        reset=False,
    )

    assert calls == ["replay"]
