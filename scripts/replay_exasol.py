from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pyexasol  # type: ignore[import-untyped]
from sss_core.config import ExasolSettings
from sss_core.demo import FixedDemoFixture, load_demo_fixture
from sss_core.repositories.exasol import ExasolDemoRepository, SchemaReadinessChecker

ROOT = Path(__file__).parents[1]
FIXTURE_PATH = ROOT / "demo/fixtures/fixed-intelligence.json"


def replay_fixture(
    connection: Any,
    fixture_path: Path,
    *,
    reset: bool = False,
) -> FixedDemoFixture:
    """Load the fixed global-evidence stage, optionally clearing all fixture-scoped demo data."""
    fixture = load_demo_fixture(fixture_path)
    repository = ExasolDemoRepository(connection)
    if reset:
        repository.reset(fixture)
    repository.replay_global_evidence(fixture)
    return fixture


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replay the fixed SSS evidence fixture into Exasol"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="clear all fixture-scoped demo stages before replaying global evidence",
    )
    arguments = parser.parse_args()
    settings = ExasolSettings.from_env()
    connection = pyexasol.connect(
        dsn=settings.dsn,
        user=settings.user,
        password=settings.password,
        schema=settings.schema,
        autocommit=False,
    )
    readiness = SchemaReadinessChecker(ROOT / "infra/exasol/migrations").check(connection)
    if not readiness.ready:
        print(
            json.dumps(
                {
                    "ready": False,
                    "schema": settings.schema,
                    "current_version": readiness.current_version,
                },
                sort_keys=True,
            )
        )
        raise SystemExit(1)

    fixture = replay_fixture(connection, FIXTURE_PATH, reset=arguments.reset)
    print(
        json.dumps(
            {
                "ready": True,
                "schema": settings.schema,
                "fixture_version": fixture.fixture_version,
                "package": fixture.package.canonical_name,
                "reset": arguments.reset,
                "recurrence": {
                    "verified_model_recommendations": fixture.verified_model_recommendations,
                    "model_configurations": fixture.model_configurations,
                    "protected_agent_attempts": fixture.protected_agent_attempts,
                    "public_failed_references": fixture.public_failed_references,
                    "observation_days": fixture.observation_days,
                },
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
