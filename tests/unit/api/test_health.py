from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException
from sss_api.routes.health import ready
from sss_core import RuntimeMode
from sss_core.repositories.exasol import SchemaReadiness


class Connection:
    def __init__(self, *, fails: bool = False) -> None:
        self.fails = fails

    def execute(self, _sql: str) -> list[tuple[int]]:
        if self.fails:
            raise RuntimeError("database unavailable")
        return [(1,)]


def _request(*, connection: Connection, schema_ready: bool = True) -> Any:
    readiness = SchemaReadiness(
        expected_version="002_operational_state",
        current_version="002_operational_state",
        missing_migrations=() if schema_ready else ("002_operational_state",),
        unexpected_migrations=(),
        checksum_mismatches=(),
        missing_views=(),
    )
    state = SimpleNamespace(
        runtime_mode=RuntimeMode.PRODUCTION,
        exasol_connection=connection,
        schema_readiness=readiness,
        settings=SimpleNamespace(policy_version="sss-hackathon-v3"),
    )
    return SimpleNamespace(app=SimpleNamespace(state=state))


@pytest.mark.asyncio
async def test_ready_requires_live_exasol_schema_and_frozen_policy() -> None:
    response = await ready(_request(connection=Connection()))

    assert response == {
        "status": "ready",
        "exasol": "ready",
        "schema_version": "002_operational_state",
        "policy_version": "sss-hackathon-v3",
    }


@pytest.mark.asyncio
async def test_ready_fails_when_schema_or_database_is_unavailable() -> None:
    with pytest.raises(HTTPException) as schema_error:
        await ready(_request(connection=Connection(), schema_ready=False))
    with pytest.raises(HTTPException) as database_error:
        await ready(_request(connection=Connection(fails=True)))

    assert schema_error.value.status_code == 503
    assert database_error.value.status_code == 503
