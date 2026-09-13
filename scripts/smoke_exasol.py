from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pyexasol  # type: ignore[import-untyped]
from sss_core.config import ExasolSettings
from sss_core.demo import load_demo_fixture
from sss_core.repositories.exasol import SchemaReadinessChecker

ROOT = Path(__file__).parents[1]


def _rows(result: Any) -> list[tuple[Any, ...]]:
    return list(result.fetchall())


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify an SSS Exasol schema")
    parser.add_argument(
        "--expect-demo",
        action="store_true",
        help="also require the fixed replay and registration-transition values",
    )
    arguments = parser.parse_args()
    settings = ExasolSettings.from_env()
    fixture = load_demo_fixture(ROOT / "demo/fixtures/fixed-intelligence.json")
    connection = pyexasol.connect(
        dsn=settings.dsn,
        user=settings.user,
        password=settings.password,
        schema=settings.schema,
        autocommit=False,
    )
    readiness = SchemaReadinessChecker(ROOT / "infra/exasol/migrations").check(connection)
    result: dict[str, object] = {
        "ready": readiness.ready,
        "schema": settings.schema,
        "current_version": readiness.current_version,
    }
    if not readiness.ready:
        print(json.dumps(result, sort_keys=True))
        raise SystemExit(1)
    if arguments.expect_demo:
        recurrence_rows = _rows(
            connection.execute(
                "SELECT VERIFIED_MODEL_RECOMMENDATIONS, MODEL_CONFIGURATIONS, "
                "PROTECTED_AGENT_ATTEMPTS, PUBLIC_FAILED_REFERENCES, OBSERVATION_DAYS "
                "FROM V_GLOBAL_RECURRENCE WHERE ECOSYSTEM={ecosystem} "
                "AND REGISTRY_ORIGIN={registry_origin} AND CANONICAL_NAME={canonical_name}",
                {
                    "ecosystem": fixture.package.ecosystem.value,
                    "registry_origin": fixture.package.registry_origin,
                    "canonical_name": fixture.package.canonical_name,
                },
            )
        )
        expected = (46, 3, 8, 5, 11)
        result["recurrence"] = recurrence_rows[0] if recurrence_rows else None
        if not recurrence_rows or tuple(int(value) for value in recurrence_rows[0]) != expected:
            print(json.dumps(result, default=str, sort_keys=True))
            raise SystemExit(1)
    print(json.dumps(result, default=str, sort_keys=True))


if __name__ == "__main__":
    main()
