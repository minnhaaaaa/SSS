from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from sss_core.repositories.exasol import SchemaReadinessChecker

ROOT = Path(__file__).parents[2]


class ReadinessConnection:
    def __init__(self, migration_rows: list[tuple[str, str]], views: list[str]) -> None:
        self.migration_rows = migration_rows
        self.views = views

    def execute(self, sql: str, query_params: Any = None) -> list[tuple[str, ...]]:
        if "SCHEMA_MIGRATIONS" in sql:
            return self.migration_rows
        if "EXA_ALL_VIEWS" in sql:
            return [(view,) for view in self.views]
        raise AssertionError(f"unexpected readiness query: {sql}")

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None


def _expected_rows() -> list[tuple[str, str]]:
    return [
        (path.stem, hashlib.sha256(path.read_bytes()).hexdigest())
        for path in sorted((ROOT / "infra/exasol/migrations").glob("[0-9][0-9][0-9]_*.sql"))
    ]


def _expected_views() -> list[str]:
    return [
        "V_VERIFIED_HALLUCINATIONS",
        "V_GLOBAL_RECURRENCE",
        "V_MODEL_PACKAGE_HALLUCINATION_RATE",
        "V_REGISTRATION_TRANSITIONS",
        "V_HIGH_ATTRACTIVENESS_WATCHLIST",
        "V_SOURCE_POLICY_VIOLATIONS",
        "V_PACKAGE_EVIDENCE_TIMELINE",
        "V_GUARD_OUTCOMES",
        "V_RADAR_PRIVATE",
        "V_RADAR_PUBLIC_AGGREGATES",
    ]


def test_schema_is_ready_only_with_all_checksums_and_views() -> None:
    checker = SchemaReadinessChecker(ROOT / "infra/exasol/migrations")

    result = checker.check(ReadinessConnection(_expected_rows(), _expected_views()))

    assert result.ready
    assert result.current_version == "001_initial_evidence"
    assert result.expected_version == "001_initial_evidence"
    assert result.missing_migrations == ()
    assert result.checksum_mismatches == ()
    assert result.missing_views == ()


def test_schema_reports_checksum_drift_and_missing_views() -> None:
    checker = SchemaReadinessChecker(ROOT / "infra/exasol/migrations")
    rows = _expected_rows()
    rows[-1] = (rows[-1][0], "0" * 64)
    views = _expected_views()[1:]

    result = checker.check(ReadinessConnection(rows, views))

    assert not result.ready
    assert result.checksum_mismatches == ("001_initial_evidence",)
    assert result.missing_views == (_expected_views()[0],)


def test_schema_rejects_unexpected_newer_migration() -> None:
    checker = SchemaReadinessChecker(ROOT / "infra/exasol/migrations")

    result = checker.check(
        ReadinessConnection([*_expected_rows(), ("999_unknown", "f" * 64)], _expected_views())
    )

    assert not result.ready
    assert result.current_version == "999_unknown"
    assert result.unexpected_migrations == ("999_unknown",)
