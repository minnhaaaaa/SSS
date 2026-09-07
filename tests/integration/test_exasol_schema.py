from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
from sss_core.repositories.exasol import MigrationRunner

ROOT = Path(__file__).parents[2]


class RecordingMigrationConnection:
    def __init__(self) -> None:
        self.applied: set[str] = set()
        self.ddl_count = 0
        self.view_count = 0

    def execute(self, sql: str, query_params: dict[str, Any] | None = None) -> Any:
        normalized = " ".join(sql.upper().split())
        if normalized.startswith("SELECT VERSION FROM SCHEMA_MIGRATIONS"):
            version = str((query_params or {})["version"])
            return [(version,)] if version in self.applied else []
        if normalized.startswith("INSERT INTO SCHEMA_MIGRATIONS"):
            self.applied.add(str((query_params or {})["version"]))
        elif (
            normalized.startswith(("CREATE TABLE", "CREATE OR REPLACE VIEW"))
            and "SCHEMA_MIGRATIONS" not in normalized
        ):
            self.ddl_count += 1
            if normalized.startswith("CREATE OR REPLACE VIEW"):
                self.view_count += 1
        return []

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None


def test_migrating_an_empty_schema_twice_is_a_noop() -> None:
    connection = RecordingMigrationConnection()
    runner = MigrationRunner(ROOT / "infra/exasol/migrations")

    first = runner.migrate(connection)
    ddl_after_first = connection.ddl_count
    second = runner.migrate(connection)

    assert first == ("001_initial_evidence",)
    assert connection.view_count == 10
    assert second == ()
    assert connection.ddl_count == ddl_after_first


@pytest.mark.skipif(
    not os.getenv("SSS_EXASOL_DSN"),
    reason="requires an explicitly provisioned Exasol Personal deployment",
)
def test_migrations_run_twice_on_exasol_personal() -> None:
    import pyexasol

    connection = pyexasol.connect(
        dsn=os.environ["SSS_EXASOL_DSN"],
        user=os.environ["SSS_EXASOL_USER"],
        password=os.environ["SSS_EXASOL_PASSWORD"],
        schema=os.environ["SSS_EXASOL_SCHEMA"],
        autocommit=False,
    )
    runner = MigrationRunner(ROOT / "infra/exasol/migrations")

    runner.migrate(connection)
    assert runner.migrate(connection) == ()
