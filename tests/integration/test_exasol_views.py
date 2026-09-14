from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb
from sss_core.demo import FixedDemoFixture, load_demo_fixture

ROOT = Path(__file__).parents[2]


def _database() -> duckdb.DuckDBPyConnection:
    database = duckdb.connect(":memory:")
    migration = ROOT / "infra/exasol/migrations/001_initial_evidence.sql"
    database.execute(migration.read_text(encoding="utf-8"))
    for view_path in sorted((ROOT / "infra/exasol/views").glob("*.sql")):
        database.execute(view_path.read_text(encoding="utf-8"))
    return database


def _insert_fixed_fixture(database: duckdb.DuckDBPyConnection) -> FixedDemoFixture:
    fixture = load_demo_fixture(ROOT / "demo/fixtures/fixed-intelligence.json")
    now = datetime(2026, 9, 7, tzinfo=UTC)
    identity = (
        fixture.package.ecosystem.value,
        fixture.package.registry_origin,
        fixture.package.canonical_name,
    )
    database.execute(
        "INSERT INTO CANDIDATES VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            *identity,
            "registered_after_absence",
            fixture.first_absence_at,
            fixture.registered_at,
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

    rows: list[list[object]] = [
        [
            *identity,
            row["provenance"],
            row["source_id"],
            row["model_configuration_id"],
            row["observed_at"],
            True,
        ]
        for row in fixture.mention_rows()
    ]
    database.executemany(
        "INSERT INTO PACKAGE_MENTIONS (ECOSYSTEM, REGISTRY_ORIGIN, CANONICAL_NAME, "
        "PROVENANCE, SOURCE_ID, MODEL_CONFIGURATION_ID, OBSERVED_AT, EXPLICIT_CONTEXT) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    return fixture


def test_fixed_fixture_produces_recurrence_and_transition_rows() -> None:
    database = _database()
    fixture = _insert_fixed_fixture(database)

    recurrence = database.execute(
        "SELECT verified_model_recommendations, model_configurations, "
        "protected_agent_attempts, public_failed_references, observation_days "
        "FROM V_GLOBAL_RECURRENCE WHERE canonical_name = ?",
        [fixture.package.canonical_name],
    ).fetchone()
    transition = database.execute(
        "SELECT canonical_name FROM V_REGISTRATION_TRANSITIONS WHERE canonical_name = ?",
        [fixture.package.canonical_name],
    ).fetchone()

    assert recurrence == (46, 3, 8, 5, 11)
    assert transition == (fixture.package.canonical_name,)


def test_private_radar_contains_name_while_public_aggregate_cannot_expose_it() -> None:
    database = _database()
    fixture = _insert_fixed_fixture(database)

    private_names = database.execute("SELECT canonical_name FROM V_RADAR_PRIVATE").fetchall()
    public_columns = {
        row[1].lower()
        for row in database.execute("PRAGMA table_info('V_RADAR_PUBLIC_AGGREGATES')").fetchall()
    }
    public_rows = database.execute("SELECT * FROM V_RADAR_PUBLIC_AGGREGATES").fetchall()

    assert (fixture.package.canonical_name,) in private_names
    assert "canonical_name" not in public_columns
    assert fixture.package.canonical_name not in repr(public_rows)
