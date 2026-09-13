from __future__ import annotations

from pathlib import Path
from typing import Any

from sss_core.demo import load_demo_fixture
from sss_core.repositories.exasol import ExasolDemoRepository

ROOT = Path(__file__).parents[2]


class RecordingConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.commits = 0
        self.rollbacks = 0

    def execute(self, sql: str, query_params: dict[str, Any] | None = None) -> list[Any]:
        self.calls.append((sql, query_params or {}))
        return []

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def test_replay_replaces_only_exact_identity_and_inserts_fixed_counts() -> None:
    fixture = load_demo_fixture(ROOT / "demo/fixtures/fixed-intelligence.json")
    connection = RecordingConnection()
    repository = ExasolDemoRepository(connection)

    repository.replay_global_evidence(fixture)

    all_sql = " ".join(sql for sql, _ in connection.calls)
    all_parameters = [parameters for _, parameters in connection.calls]
    mention_inserts = [
        sql for sql, _ in connection.calls if sql.startswith("INSERT INTO PACKAGE_MENTIONS")
    ]
    assert fixture.package.canonical_name not in all_sql
    assert "'{}'" not in all_sql
    assert any(parameters.get("parameters_json") == "{}" for parameters in all_parameters)
    assert any(
        parameters.get("canonical_name") == fixture.package.canonical_name
        for parameters in all_parameters
    )
    assert len(mention_inserts) == 46 + 8 + 5
    bound_timestamps = [
        value
        for parameters in all_parameters
        for value in parameters.values()
        if hasattr(value, "tzinfo")
    ]
    assert bound_timestamps
    assert all(timestamp.tzinfo is None for timestamp in bound_timestamps)
    assert connection.commits == 1
    assert connection.rollbacks == 0


def test_reset_and_replay_are_each_transactional() -> None:
    fixture = load_demo_fixture(ROOT / "demo/fixtures/fixed-intelligence.json")
    connection = RecordingConnection()
    repository = ExasolDemoRepository(connection)

    repository.reset(fixture)
    repository.replay_global_evidence(fixture)
    repository.replay_global_evidence(fixture)

    assert connection.commits == 3
    assert connection.rollbacks == 0
    assert all(
        "canonical_name" not in parameters
        or parameters["canonical_name"] == fixture.package.canonical_name
        for _, parameters in connection.calls
    )
