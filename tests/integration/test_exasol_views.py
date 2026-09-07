from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb

ROOT = Path(__file__).parents[2]
SYNTHETIC_NAME = "sss-reserved-synthetic"


def _database() -> duckdb.DuckDBPyConnection:
    database = duckdb.connect(":memory:")
    migration = ROOT / "infra/exasol/migrations/001_initial_evidence.sql"
    database.execute(migration.read_text(encoding="utf-8"))
    for view_path in sorted((ROOT / "infra/exasol/views").glob("*.sql")):
        database.execute(view_path.read_text(encoding="utf-8"))
    return database


def _insert_fixed_fixture(database: duckdb.DuckDBPyConnection) -> None:
    now = datetime(2026, 9, 7, tzinfo=UTC)
    identity = ("npm", "https://registry.npmjs.org", SYNTHETIC_NAME)
    database.execute(
        "INSERT INTO CANDIDATES VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            *identity,
            "registered_after_absence",
            now - timedelta(days=11),
            now - timedelta(minutes=43),
            "restricted_target_intelligence",
            True,
        ],
    )
    database.execute(
        "INSERT INTO CANDIDATES VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            "pypi",
            "https://pypi.org",
            "established-safe",
            "registered",
            None,
            now - timedelta(days=500),
            "public",
            False,
        ],
    )

    rows: list[list[object]] = []
    for index in range(46):
        rows.append(
            [
                *identity,
                "model_probe",
                f"run-{index}",
                f"model-{index % 3}",
                now - timedelta(days=index % 11),
                True,
            ]
        )
    for index in range(8):
        rows.append(
            [
                *identity,
                "agent_install_attempt",
                f"client-{index}",
                None,
                now,
                True,
            ]
        )
    for index in range(5):
        rows.append(
            [
                *identity,
                "public_ci_failure",
                f"public-{index}",
                None,
                now,
                True,
            ]
        )
    database.executemany(
        "INSERT INTO PACKAGE_MENTIONS (ECOSYSTEM, REGISTRY_ORIGIN, CANONICAL_NAME, "
        "PROVENANCE, SOURCE_ID, MODEL_CONFIGURATION_ID, OBSERVED_AT, EXPLICIT_CONTEXT) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )


def test_fixed_fixture_produces_recurrence_and_transition_rows() -> None:
    database = _database()
    _insert_fixed_fixture(database)

    recurrence = database.execute(
        "SELECT verified_model_recommendations, model_configurations, "
        "protected_agent_attempts, public_failed_references, observation_days "
        "FROM V_GLOBAL_RECURRENCE WHERE canonical_name = ?",
        [SYNTHETIC_NAME],
    ).fetchone()
    transition = database.execute(
        "SELECT canonical_name FROM V_REGISTRATION_TRANSITIONS WHERE canonical_name = ?",
        [SYNTHETIC_NAME],
    ).fetchone()

    assert recurrence == (46, 3, 8, 5, 11)
    assert transition == (SYNTHETIC_NAME,)


def test_private_radar_contains_name_while_public_aggregate_cannot_expose_it() -> None:
    database = _database()
    _insert_fixed_fixture(database)

    private_names = database.execute("SELECT canonical_name FROM V_RADAR_PRIVATE").fetchall()
    public_columns = {
        row[1].lower()
        for row in database.execute("PRAGMA table_info('V_RADAR_PUBLIC_AGGREGATES')").fetchall()
    }
    public_rows = database.execute("SELECT * FROM V_RADAR_PUBLIC_AGGREGATES").fetchall()

    assert (SYNTHETIC_NAME,) in private_names
    assert "canonical_name" not in public_columns
    assert SYNTHETIC_NAME not in repr(public_rows)
