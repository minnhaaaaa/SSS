"""Record the deterministic synthetic registration transition in local Exasol."""

from __future__ import annotations

from pathlib import Path

import pyexasol  # type: ignore[import-untyped]
from sss_core.config import ExasolSettings
from sss_core.demo import load_demo_fixture
from sss_core.repositories.exasol import ExasolDemoRepository

ROOT = Path(__file__).parents[1]


def main() -> None:
    settings = ExasolSettings.from_env()
    connection = pyexasol.connect(
        dsn=settings.dsn,
        user=settings.user,
        password=settings.password,
        schema=settings.schema,
        autocommit=False,
    )
    fixture = load_demo_fixture(ROOT / "demo/fixtures/fixed-intelligence.json")
    ExasolDemoRepository(connection).record_registration(fixture)
    print(
        {
            "registered": fixture.package.canonical_name,
            "origin": fixture.registration_origin,
            "version": "1.0.0",
        }
    )


if __name__ == "__main__":
    main()
