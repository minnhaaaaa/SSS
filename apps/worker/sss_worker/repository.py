"""Durable Exasol cursors, leases, and model observations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sss_core import CandidateStatus, Ecosystem
from sss_core.repositories.exasol import ExasolConnection

from sss_worker.jobs.probe import CollectedObservation


def _rows(result: Any) -> list[tuple[Any, ...]]:
    value = result.fetchall() if hasattr(result, "fetchall") else result
    return cast(list[tuple[Any, ...]], value)


def _timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _database_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return _timestamp(value)
    return datetime.fromisoformat(str(value))


class WorkerRepository:
    def __init__(self, connection: ExasolConnection) -> None:
        self._connection = connection

    def acquire_lease(
        self, job_name: str, owner: str, *, now: datetime, ttl: timedelta
    ) -> bool:
        params = {
            "job": job_name,
            "owner": owner,
            "now": _timestamp(now),
            "expires": _timestamp(now + ttl),
        }
        try:
            self._connection.execute(
                "MERGE INTO WORKER_LEASES L USING (SELECT {job} JOB_NAME FROM DUAL) S "
                "ON L.JOB_NAME=S.JOB_NAME WHEN MATCHED THEN UPDATE SET "
                "L.LEASE_OWNER={owner}, L.ACQUIRED_AT={now}, L.EXPIRES_AT={expires} "
                "WHERE L.EXPIRES_AT<={now} WHEN NOT MATCHED THEN INSERT "
                "(JOB_NAME, LEASE_OWNER, ACQUIRED_AT, EXPIRES_AT) VALUES "
                "({job}, {owner}, {now}, {expires})",
                params,
            )
            rows = _rows(
                self._connection.execute(
                    "SELECT LEASE_OWNER, EXPIRES_AT FROM WORKER_LEASES WHERE JOB_NAME={job}",
                    params,
                )
            )
            # Exasol serializes TIMESTAMP values at millisecond precision through
            # PyExasol. The owner is unique per worker run and is read before this
            # transaction commits, so it is the reliable acquisition predicate.
            acquired = bool(rows and str(rows[0][0]) == owner)
            self._connection.commit()
            return acquired
        except Exception as error:
            self._connection.rollback()
            try:
                rows = _rows(
                    self._connection.execute(
                        "SELECT LEASE_OWNER, EXPIRES_AT FROM WORKER_LEASES "
                        "WHERE JOB_NAME={job}",
                        params,
                    )
                )
            except Exception as query_error:
                raise error from query_error
            if (
                rows
                and str(rows[0][0]) != owner
                and _database_timestamp(rows[0][1]) > cast(datetime, params["now"])
            ):
                return False
            raise

    def heartbeat(
        self, job_name: str, owner: str, *, now: datetime, ttl: timedelta
    ) -> bool:
        result = self._connection.execute(
            "UPDATE WORKER_LEASES SET EXPIRES_AT={expires} WHERE JOB_NAME={job} "
            "AND LEASE_OWNER={owner} AND EXPIRES_AT>{now}",
            {
                "job": job_name,
                "owner": owner,
                "now": _timestamp(now),
                "expires": _timestamp(now + ttl),
            },
        )
        self._connection.commit()
        return int(getattr(result, "rowcount", 0)) == 1

    def release(self, job_name: str, owner: str) -> None:
        self._connection.execute(
            "DELETE FROM WORKER_LEASES WHERE JOB_NAME={job} AND LEASE_OWNER={owner}",
            {"job": job_name, "owner": owner},
        )
        self._connection.commit()

    def cursor(self, job_name: str, source_id: str) -> str | None:
        storage_job = f"{job_name}:{source_id}"
        rows = _rows(
            self._connection.execute(
                "SELECT CURSOR_VALUE FROM WORKER_JOBS WHERE JOB_NAME={job}",
                {"job": storage_job},
            )
        )
        return None if not rows else rows[0][0]

    def finish(
        self,
        job_name: str,
        source_id: str,
        *,
        outcome: str,
        cursor: str | None,
        data_as_of: datetime,
    ) -> None:
        params = {
            "job": f"{job_name}:{source_id}",
            "source": source_id,
            "cursor": cursor,
            "outcome": outcome,
            "data_as_of": _timestamp(data_as_of),
            "updated_at": _timestamp(datetime.now(UTC)),
        }
        self._connection.execute(
            "MERGE INTO WORKER_JOBS J USING (SELECT {job} JOB_NAME FROM DUAL) S "
            "ON J.JOB_NAME=S.JOB_NAME WHEN MATCHED THEN UPDATE SET "
            "J.CURSOR_VALUE=CASE WHEN {outcome}='success' THEN {cursor} "
            "ELSE J.CURSOR_VALUE END, J.OUTCOME={outcome}, J.DATA_AS_OF={data_as_of}, "
            "J.UPDATED_AT={updated_at} WHEN NOT MATCHED THEN INSERT (JOB_NAME, SOURCE_ID, "
            "CURSOR_VALUE, OUTCOME, DATA_AS_OF, UPDATED_AT) VALUES ({job}, {source}, "
            "CASE WHEN {outcome}='success' THEN {cursor} ELSE NULL END, {outcome}, "
            "{data_as_of}, {updated_at})",
            params,
        )
        self._connection.commit()


class ExasolModelObservationSink:
    """Idempotently persist model mentions without provider response bodies."""

    def __init__(self, connection: ExasolConnection) -> None:
        self._connection = connection

    def record(self, observation: CollectedObservation) -> bool:
        existing = _rows(
            self._connection.execute(
                "SELECT MENTION_ID FROM PACKAGE_MENTIONS WHERE MENTION_ID={mention_id}",
                {"mention_id": observation.observation_id},
            )
        )
        if existing:
            return False
        origin = (
            "https://registry.npmjs.org"
            if observation.ecosystem is Ecosystem.NPM
            else "https://pypi.org/simple"
        )
        params = {
            "mention_id": observation.observation_id,
            "ecosystem": observation.ecosystem.value,
            "origin": origin,
            "name": observation.canonical_name,
            "source_id": observation.source_id,
            "configuration": observation.model_configuration_sha256,
            "observed_at": _timestamp(datetime.now(UTC)),
            "status": CandidateStatus.AMBIGUOUS.value,
        }
        try:
            self._connection.execute(
                "MERGE INTO CANDIDATES C USING (SELECT {ecosystem} ECOSYSTEM, {origin} "
                "REGISTRY_ORIGIN, {name} CANONICAL_NAME FROM DUAL) S ON "
                "C.ECOSYSTEM=S.ECOSYSTEM AND C.REGISTRY_ORIGIN=S.REGISTRY_ORIGIN AND "
                "C.CANONICAL_NAME=S.CANONICAL_NAME WHEN NOT MATCHED THEN INSERT "
                "(ECOSYSTEM, REGISTRY_ORIGIN, CANONICAL_NAME, STATUS, DISCLOSURE_CLASS, "
                "SYNTHETIC) VALUES ({ecosystem}, {origin}, {name}, {status}, "
                "'restricted_target_intelligence', FALSE)",
                params,
            )
            self._connection.execute(
                "INSERT INTO PACKAGE_MENTIONS (MENTION_ID, ECOSYSTEM, REGISTRY_ORIGIN, "
                "CANONICAL_NAME, PROVENANCE, SOURCE_ID, MODEL_CONFIGURATION_ID, OBSERVED_AT, "
                "CONTEXT_KIND, CONFIDENCE, EXPLICIT_CONTEXT) VALUES ({mention_id}, "
                "{ecosystem}, {origin}, {name}, 'model_probe', {source_id}, {configuration}, "
                "{observed_at}, 'install', 1, TRUE)",
                params,
            )
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raced = _rows(
                self._connection.execute(
                    "SELECT MENTION_ID FROM PACKAGE_MENTIONS WHERE MENTION_ID={mention_id}",
                    {"mention_id": observation.observation_id},
                )
            )
            if raced:
                return False
            raise
        return True
