from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pyexasol  # type: ignore[import-untyped]
from sss_core.config import ExasolSettings
from sss_core.repositories.exasol import MigrationRunner, SchemaReadinessChecker

ROOT = Path(__file__).parents[1]


def _connect(settings: ExasolSettings) -> Any:
    return pyexasol.connect(
        dsn=settings.dsn,
        user=settings.user,
        password=settings.password,
        autocommit=False,
    )


def main() -> None:
    settings = ExasolSettings.from_env()
    connection = _connect(settings)
    quoted_schema = f'"{settings.schema}"'
    connection.execute(f"CREATE SCHEMA IF NOT EXISTS {quoted_schema}")
    connection.execute(f"OPEN SCHEMA {quoted_schema}")
    runner = MigrationRunner(ROOT / "infra/exasol/migrations")
    applied = runner.migrate(connection)
    readiness = SchemaReadinessChecker(ROOT / "infra/exasol/migrations").check(connection)
    print(
        json.dumps(
            {
                "ready": readiness.ready,
                "schema": settings.schema,
                "current_version": readiness.current_version,
                "expected_version": readiness.expected_version,
                "applied": applied,
                "missing_migrations": readiness.missing_migrations,
                "unexpected_migrations": readiness.unexpected_migrations,
                "checksum_mismatches": readiness.checksum_mismatches,
                "missing_views": readiness.missing_views,
            },
            sort_keys=True,
        )
    )
    if not readiness.ready:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
