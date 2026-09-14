from __future__ import annotations

import os
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sss_core import Ecosystem, EvidenceProvenance
from sss_core.repositories.exasol import MigrationRunner
from sss_worker.config import WorkerSettings
from sss_worker.jobs.probe import make_observation
from sss_worker.repository import ExasolModelObservationSink, WorkerRepository

ROOT = Path(__file__).parents[2]


def test_worker_allows_explicit_private_http_model_and_secret_file(tmp_path) -> None:  # type: ignore[no-untyped-def]
    token = tmp_path / "model-token"
    token.write_text("local-secret\n", encoding="utf-8")
    token.chmod(0o600)

    settings = WorkerSettings.from_env(
        {
            "SSS_ENV": "production",
            "SSS_MODEL_BASE_URL": "http://127.0.0.1:11434",
            "SSS_MODEL_ID": "local-code-model",
            "SSS_MODEL_TOKEN_FILE": str(token),
            "SSS_ALLOW_PRIVATE_HTTP_MODEL": "true",
        }
    )

    assert settings.read_model_token() == "local-secret"


@pytest.mark.skipif(
    not os.getenv("SSS_EXASOL_DSN"),
    reason="requires an explicitly provisioned Exasol database",
)
def test_live_worker_cursor_lease_and_observation_survive_restart() -> None:
    import pyexasol

    suffix = uuid4().hex
    job_name = f"worker-live-{suffix}"

    def connect():  # type: ignore[no-untyped-def]
        return pyexasol.connect(
            dsn=os.environ["SSS_EXASOL_DSN"],
            user=os.environ["SSS_EXASOL_USER"],
            password=os.environ["SSS_EXASOL_PASSWORD"],
            schema=os.environ["SSS_EXASOL_SCHEMA"],
            autocommit=False,
        )

    first_connection = connect()
    second_connection = None
    try:
        MigrationRunner(ROOT / "infra/exasol/migrations").migrate(first_connection)
        first = WorkerRepository(first_connection)
        now = datetime.now(UTC)
        assert first.acquire_lease(
            job_name, f"first-{suffix}", now=now, ttl=timedelta(minutes=1)
        )
        first.finish(
            job_name,
            suffix,
            outcome="success",
            cursor="cursor-1",
            data_as_of=now,
        )
        observation = make_observation(
            provenance=EvidenceProvenance.MODEL_PROBE,
            source_id=f"model-run-{suffix}",
            ecosystem=Ecosystem.NPM,
            canonical_name=f"worker-live-{suffix}",
            model_configuration_sha256="a" * 64,
        )
        assert ExasolModelObservationSink(first_connection).record(observation)
        first.release(job_name, f"first-{suffix}")
        first_connection.close()

        second_connection = connect()
        restarted = WorkerRepository(second_connection)
        assert restarted.cursor(job_name, suffix) == "cursor-1"
        assert not ExasolModelObservationSink(second_connection).record(observation)
    finally:
        with suppress(Exception):
            first_connection.close()
        if second_connection is not None:
            second_connection.close()
