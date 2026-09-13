from __future__ import annotations

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier
from typing import Any
from uuid import uuid4

import pytest
from sss_api.services.attempts import InstallAttempt
from sss_api.services.interventions import Intervention, InterventionStatus
from sss_core import Decision, Ecosystem, EvidenceScores, InstallRequest, PackageIdentity
from sss_core.domain import PolicyDecision

from tests.integration.test_exasol_schema import RecordingMigrationConnection

ROOT = Path(__file__).parents[2]
DEMO_IDENTITY = PackageIdentity(
    Ecosystem.NPM,
    "https://registry.npmjs.org",
    "hostile'}; DROP TABLE EVENT_LOG; --",
)
NOW = datetime(2026, 9, 13, 9, 30, tzinfo=UTC)


class StatementResult:
    def __init__(self, rows: list[tuple[Any, ...]], *, rowcount: int = 0) -> None:
        self._rows = rows
        self.rowcount = rowcount

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._rows


class RecordingOperationalConnection:
    """Stateful Exasol boundary fake; repository instances share only this state."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any] | None]] = []
        self.commits = 0
        self.rollbacks = 0
        self.attempts: dict[str, dict[str, Any]] = {}
        self.interventions: dict[str, dict[str, Any]] = {}
        self.claims: dict[str, dict[str, Any]] = {}
        self.events: dict[int, dict[str, Any]] = {}
        self.approvals: dict[str, dict[str, Any]] = {}

    def execute(
        self, sql: str, query_params: dict[str, Any] | None = None
    ) -> StatementResult:
        params = query_params or {}
        self.calls.append((sql, query_params))
        normalized = " ".join(sql.upper().split())
        if normalized.startswith("INSERT INTO INSTALL_ATTEMPTS"):
            if str(params["attempt_id"]) in self.attempts:
                raise RuntimeError("unique constraint violation")
            self.attempts[str(params["attempt_id"])] = dict(params)
            return StatementResult([], rowcount=1)
        if normalized.startswith("SELECT ATTEMPT_ID"):
            if "WHERE ATTEMPT_ID={ATTEMPT_ID}" in normalized:
                row = self.attempts.get(str(params["attempt_id"]))
                rows = [] if row is None else [row]
            else:
                rows = sorted(
                    self.attempts.values(), key=lambda row: row["attempted_at"], reverse=True
                )[: int(params["limit"])]
            return StatementResult(
                [
                    (
                        row["attempt_id"],
                        row["decision_id"],
                        row["manager"],
                        row["arguments_json"],
                        row["agent_family"],
                        row["project_id"],
                        row["decision"],
                        row["child_started"],
                        row["attempted_at"],
                    )
                    for row in rows
                ]
            )
        if normalized.startswith("INSERT INTO INTERVENTIONS"):
            if str(params["intervention_id"]) in self.interventions:
                raise RuntimeError("unique constraint violation")
            self.interventions[str(params["intervention_id"])] = dict(params)
            return StatementResult([], rowcount=1)
        if normalized.startswith("SELECT INTERVENTION_ID"):
            if "WHERE INTERVENTION_ID={INTERVENTION_ID}" in normalized:
                row = self.interventions.get(str(params["intervention_id"]))
                rows = [] if row is None else [row]
            else:
                rows = list(self.interventions.values())
            if "STATUS={PENDING_STATUS}" in normalized:
                rows = [row for row in rows if row["status"] == params["pending_status"]]
            rows = sorted(rows, key=lambda row: row["created_at"], reverse=True)
            if "limit" in params:
                rows = rows[: int(params["limit"])]
            return StatementResult(
                [
                    (
                        row["intervention_id"],
                        row["request_json"],
                        row["decision_json"],
                        row["evidence_labels_json"],
                        row["status"],
                        row["created_at"],
                        row["approval_id"],
                    )
                    for row in rows
                ]
            )
        if normalized.startswith("UPDATE INTERVENTIONS"):
            row = self.interventions.get(str(params["intervention_id"]))
            if row is None or row["status"] != params["pending_status"]:
                return StatementResult([], rowcount=0)
            row.update(
                status=params["status"],
                approval_id=params["approval_id"],
                resolved_at=params["resolved_at"],
            )
            return StatementResult([], rowcount=1)
        if normalized.startswith("SELECT REQUEST_HASH"):
            row = self.claims.get(str(params["idempotency_key"]))
            if row is None:
                return StatementResult([])
            return StatementResult(
                [(row["request_hash"], row["response_reference"], row["created_at"])]
            )
        if normalized.startswith("INSERT INTO IDEMPOTENCY_CLAIMS"):
            key = str(params["idempotency_key"])
            if key in self.claims:
                raise RuntimeError("unique constraint violation")
            self.claims[key] = dict(params)
            return StatementResult([], rowcount=1)
        if normalized.startswith("INSERT INTO EVENT_LOG"):
            event_id = max(self.events, default=0) + 1
            self.events[event_id] = {**params, "event_id": event_id}
            return StatementResult([], rowcount=1)
        if normalized.startswith("SELECT EVENT_ID FROM EVENT_LOG WHERE EVENT_KEY"):
            for event_id, row in self.events.items():
                if row["event_key"] == params["event_key"]:
                    return StatementResult([(event_id,)])
            return StatementResult([])
        if normalized.startswith("SELECT EVENT_ID"):
            rows = [
                row
                for event_id, row in sorted(self.events.items())
                if event_id > int(params["after_id"])
            ][: int(params["limit"])]
            return StatementResult(
                [
                    (
                        row["event_id"],
                        row["event_type"],
                        row["payload_json"],
                        row["occurred_at"],
                    )
                    for row in rows
                ]
            )
        if normalized.startswith("UPDATE APPROVAL_GRANTS"):
            row = self.approvals.get(str(params["approval_id"]))
            if (
                row is None
                or row["nonce"] != params["nonce"]
                or row["request_id"] != params["request_id"]
                or row["expires_at"] <= params["consumed_at"]
                or row["consumed_at"] is not None
            ):
                return StatementResult([], rowcount=0)
            row.update(
                consumed_at=params["consumed_at"],
                consumed_request_id=params["request_id"],
                consumption_metadata_json=params["metadata_json"],
            )
            return StatementResult([], rowcount=1)
        return StatementResult([])

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def request_fixture() -> InstallRequest:
    return InstallRequest(
        request_id="request-1",
        project_id="project-1",
        agent_family="codex",
        package=DEMO_IDENTITY,
        version_spec="1.0.0",
        direct_url=None,
        artifact_sha256="a" * 64,
        is_direct=True,
    )


def decision_fixture() -> PolicyDecision:
    return PolicyDecision(
        decision_id="decision-1",
        request_id="request-1",
        decision=Decision.BLOCK,
        reason_codes=("UNKNOWN_REGISTRY_STATE",),
        scores=EvidenceScores(None, 62, 75),
        policy_version="policy-1",
        expires_at=None,
    )


def attempt_fixture(*, child_started: bool) -> InstallAttempt:
    return InstallAttempt(
        decision_id="decision-1",
        manager="pnpm",
        arguments=("add", DEMO_IDENTITY.canonical_name),
        agent_family="codex",
        project_id="project-1",
        decision=Decision.BLOCK,
        child_started=child_started,
        attempted_at=NOW,
    )


def intervention_fixture() -> Intervention:
    return Intervention(
        intervention_id="intervention-1",
        request=request_fixture(),
        decision=decision_fixture(),
        evidence_labels=("registry state unknown",),
        status=InterventionStatus.PENDING,
        created_at=NOW,
    )


def test_operational_migration_is_ordered_and_idempotent() -> None:
    from sss_core.repositories.exasol import MigrationRunner

    connection = RecordingMigrationConnection()
    runner = MigrationRunner(ROOT / "infra/exasol/migrations")

    assert runner.migrate(connection) == (
        "001_initial_evidence",
        "002_operational_state",
    )
    assert runner.migrate(connection) == ()


def test_attempt_and_intervention_survive_repository_recreation() -> None:
    from sss_core.repositories.exasol import ExasolOperationalRepository

    connection = RecordingOperationalConnection()
    first = ExasolOperationalRepository(connection)
    first.record_attempt(attempt_fixture(child_started=False))
    first.create_intervention(intervention_fixture())

    second = ExasolOperationalRepository(connection)

    assert second.list_attempts(limit=10)[0].child_started is False
    assert second.list_interventions(pending_only=True, limit=10)[0].package == DEMO_IDENTITY
    assert all(DEMO_IDENTITY.canonical_name not in sql for sql, _ in connection.calls)
    assert all(params is not None for sql, params in connection.calls if "{" in sql)


def test_idempotency_conflict_preserves_original_response() -> None:
    from sss_core.repositories.exasol import ExasolOperationalRepository
    from sss_core.repositories.operations import IdempotencyConflict

    connection = RecordingOperationalConnection()
    repository = ExasolOperationalRepository(connection)
    original = repository.claim_idempotency("key-1", "hash-a", "decision-a")

    with pytest.raises(IdempotencyConflict):
        repository.claim_idempotency("key-1", "hash-b", "decision-b")

    assert repository.get_idempotency("key-1") == original
    assert original.request_hash == "hash-a"
    assert original.response_reference == "decision-a"
    assert connection.commits == 1
    assert connection.rollbacks == 1


def test_events_after_uses_numeric_ordering_and_bounded_limit() -> None:
    from sss_core.repositories.exasol import ExasolOperationalRepository

    connection = RecordingOperationalConnection()
    repository = ExasolOperationalRepository(connection)
    for index in range(12):
        repository.append_event(
            "install.blocked",
            {"ordinal": index + 1, "unsafe": DEMO_IDENTITY.canonical_name},
            occurred_at=NOW + timedelta(seconds=index),
        )

    events = repository.events_after(after_id=9, limit=3)

    assert [event.event_id for event in events] == [10, 11, 12]
    assert events[0].payload["ordinal"] == 10
    select_sql, select_params = connection.calls[-1]
    assert "ORDER BY EVENT_ID ASC" in " ".join(select_sql.upper().split())
    assert select_params == {"after_id": 9, "limit": 3}
    assert DEMO_IDENTITY.canonical_name not in select_sql
    for invalid in (0, 1001):
        with pytest.raises(ValueError, match="limit"):
            repository.events_after(after_id=0, limit=invalid)


def test_approval_nonce_consumption_is_compare_and_set() -> None:
    from sss_core.repositories.exasol import ExasolOperationalRepository
    from sss_core.repositories.operations import ApprovalNonceConflict

    connection = RecordingOperationalConnection()
    connection.approvals["approval-1"] = {
        "nonce": "nonce-1",
        "request_id": "request-1",
        "expires_at": (NOW + timedelta(minutes=5)).replace(tzinfo=None),
        "consumed_at": None,
        "consumed_request_id": None,
        "consumption_metadata_json": None,
    }
    repository = ExasolOperationalRepository(connection)

    repository.consume_approval_nonce(
        "approval-1",
        "nonce-1",
        "request-1",
        consumed_at=NOW,
        metadata={"agent": "codex"},
    )
    with pytest.raises(ApprovalNonceConflict):
        repository.consume_approval_nonce(
            "approval-1",
            "nonce-1",
            "request-2",
            consumed_at=NOW + timedelta(seconds=1),
            metadata={"agent": "claude"},
        )

    assert connection.approvals["approval-1"]["consumed_request_id"] == "request-1"
    assert connection.commits == 1
    assert connection.rollbacks == 1


def test_approval_nonce_rejects_wrong_request_and_expired_first_use() -> None:
    from sss_core.repositories.exasol import ExasolOperationalRepository
    from sss_core.repositories.operations import ApprovalNonceConflict

    connection = RecordingOperationalConnection()
    connection.approvals["approval-1"] = {
        "nonce": "nonce-1",
        "request_id": "request-1",
        "expires_at": (NOW + timedelta(minutes=5)).replace(tzinfo=None),
        "consumed_at": None,
        "consumed_request_id": None,
        "consumption_metadata_json": None,
    }
    repository = ExasolOperationalRepository(connection)

    with pytest.raises(ApprovalNonceConflict):
        repository.consume_approval_nonce(
            "approval-1", "nonce-1", "request-other", consumed_at=NOW, metadata={}
        )
    with pytest.raises(ApprovalNonceConflict):
        repository.consume_approval_nonce(
            "approval-1",
            "nonce-1",
            "request-1",
            consumed_at=NOW + timedelta(minutes=6),
            metadata={},
        )

    assert connection.approvals["approval-1"]["consumed_at"] is None


def test_decision_values_are_bound_and_transactional() -> None:
    from sss_core.repositories.exasol import ExasolOperationalRepository

    connection = RecordingOperationalConnection()
    repository = ExasolOperationalRepository(connection)

    repository.record_decision(
        request_fixture(),
        decision_fixture(),
        evidence_as_of=NOW,
        evidence_attestation="b" * 64,
    )

    sql, params = connection.calls[-1]
    assert DEMO_IDENTITY.canonical_name not in sql
    assert params is not None
    assert params["canonical_name"] == DEMO_IDENTITY.canonical_name
    assert params["evidence_as_of"] == NOW.replace(tzinfo=None)
    assert connection.commits == 1


def test_attempt_store_replays_original_durable_attempt() -> None:
    from sss_api.services.attempts import AttemptStore
    from sss_core.repositories.exasol import ExasolOperationalRepository

    connection = RecordingOperationalConnection()
    first = AttemptStore(repository=ExasolOperationalRepository(connection))
    original = first.record("attempt-key", attempt_fixture(child_started=False))

    second = AttemptStore(repository=ExasolOperationalRepository(connection))
    replayed = second.record(
        "attempt-key",
        replace(original, attempted_at=NOW + timedelta(minutes=5)),
    )

    assert replayed == original
    assert second.list_all() == (original,)
    assert len(connection.attempts) == 1


def test_attempt_store_keeps_identical_payloads_for_different_keys() -> None:
    from sss_api.services.attempts import AttemptStore
    from sss_core.repositories.exasol import ExasolOperationalRepository

    connection = RecordingOperationalConnection()
    store = AttemptStore(repository=ExasolOperationalRepository(connection))
    original = attempt_fixture(child_started=False)

    first = store.record("attempt-key-1", original)
    second = store.record(
        "attempt-key-2",
        replace(original, attempted_at=NOW + timedelta(minutes=5)),
    )

    assert first.attempted_at == NOW
    assert second.attempted_at == NOW + timedelta(minutes=5)
    assert len(store.list_all()) == 2


def test_intervention_store_reads_and_resolves_durable_state() -> None:
    from sss_api.services.interventions import InterventionStore
    from sss_core.repositories.exasol import ExasolOperationalRepository

    connection = RecordingOperationalConnection()
    first = InterventionStore(repository=ExasolOperationalRepository(connection))
    fixture = replace(
        intervention_fixture(),
        intervention_id=intervention_fixture().decision.decision_id,
    )
    created = first.create(
        fixture.request,
        fixture.decision,
        evidence_labels=fixture.evidence_labels,
        created_at=fixture.created_at,
    )

    second = InterventionStore(repository=ExasolOperationalRepository(connection))
    resolved = second.keep_blocked(created.intervention_id, resolved_at=NOW)

    assert resolved.status is InterventionStatus.KEPT_BLOCKED
    assert second.list_pending() == ()


@pytest.mark.asyncio
async def test_event_broker_resumes_from_durable_numeric_ids() -> None:
    from sss_api.events import EventBroker
    from sss_core.repositories.exasol import ExasolOperationalRepository

    connection = RecordingOperationalConnection()
    first = EventBroker(
        capacity=10,
        repository=ExasolOperationalRepository(connection),
    )
    await first.publish("first", {"value": 1})
    second_event = await first.publish("second", {"value": 2})

    second = EventBroker(
        capacity=10,
        repository=ExasolOperationalRepository(connection),
    )

    assert second.snapshot(after_id=1) == (second_event,)


@pytest.mark.asyncio
async def test_durable_event_stream_observes_same_and_second_broker_publications() -> None:
    from sss_api.events import EventBroker
    from sss_core.repositories.exasol import ExasolOperationalRepository

    connection = RecordingOperationalConnection()
    first = EventBroker(
        capacity=10, repository=ExasolOperationalRepository(connection), poll_interval=0.01
    )
    second = EventBroker(
        capacity=10, repository=ExasolOperationalRepository(connection), poll_interval=0.01
    )
    stream = first.stream()

    await first.publish("same", {"value": 1})
    same = await asyncio.wait_for(anext(stream), timeout=0.2)
    await second.publish("other", {"value": 2})
    other = await asyncio.wait_for(anext(stream), timeout=0.2)
    await stream.aclose()

    assert (same.event_type, other.event_type) == ("same", "other")


def test_attempt_store_replays_after_duplicate_insert_race() -> None:
    from sss_api.services.attempts import AttemptStore
    from sss_core.repositories.exasol import ExasolOperationalRepository

    connection = RecordingOperationalConnection()
    repository = ExasolOperationalRepository(connection)
    store = AttemptStore(repository=repository)
    original = store.record("attempt-key", attempt_fixture(child_started=False))

    connection.claims.clear()
    replayed = store.record("attempt-key", original)

    assert replayed == original
    assert len(connection.attempts) == 1


def test_intervention_replay_uses_exact_lookup_beyond_list_window() -> None:
    from sss_api.services.interventions import InterventionStore
    from sss_core.repositories.exasol import ExasolOperationalRepository

    connection = RecordingOperationalConnection()
    repository = ExasolOperationalRepository(connection)
    fixture = replace(
        intervention_fixture(),
        intervention_id=intervention_fixture().decision.decision_id,
    )
    repository.create_intervention(fixture)
    for index in range(1001):
        newer = replace(
            fixture,
            intervention_id=f"newer-{index}",
            created_at=NOW + timedelta(seconds=index + 1),
        )
        repository.create_intervention(newer)

    replayed = InterventionStore(repository=repository).create(
        fixture.request,
        fixture.decision,
        evidence_labels=fixture.evidence_labels,
        created_at=fixture.created_at,
    )

    assert replayed == fixture
    assert len(connection.interventions) == 1002


def test_intervention_create_and_resolution_are_idempotent() -> None:
    from sss_api.services.interventions import InterventionStore
    from sss_core.repositories.exasol import ExasolOperationalRepository

    connection = RecordingOperationalConnection()
    repository = ExasolOperationalRepository(connection)
    fixture = intervention_fixture()
    repository.create_intervention(fixture)
    store = InterventionStore(repository=repository)

    created = store.create(
        fixture.request,
        fixture.decision,
        evidence_labels=fixture.evidence_labels,
        created_at=fixture.created_at,
    )
    first = store.keep_blocked(created.intervention_id, resolved_at=NOW)
    replay = store.keep_blocked(created.intervention_id, resolved_at=NOW + timedelta(seconds=1))

    assert replay == first


def test_idempotency_hash_is_canonical_and_does_not_expose_payload() -> None:
    from sss_api.idempotency import idempotency_request_hash

    first = idempotency_request_hash({"b": 2, "a": DEMO_IDENTITY.canonical_name})
    second = idempotency_request_hash({"a": DEMO_IDENTITY.canonical_name, "b": 2})

    assert first == second
    assert len(first) == 64
    assert DEMO_IDENTITY.canonical_name not in first


@pytest.mark.skipif(
    not os.getenv("SSS_EXASOL_DSN"),
    reason="requires an explicitly provisioned Exasol database",
)
def test_live_operational_state_survives_connection_recreation() -> None:
    import pyexasol
    from sss_core.repositories.exasol import ExasolOperationalRepository
    from sss_core.repositories.operations import ApprovalNonceConflict

    suffix = uuid4().hex
    decision_id = f"task3-decision-{suffix}"
    request_id = f"task3-request-{suffix}"
    intervention_id = decision_id
    approval_id = f"task3-approval-{suffix}"
    idempotency_key = f"task3:{suffix}"
    request = replace(
        request_fixture(),
        request_id=request_id,
        package=replace(DEMO_IDENTITY, canonical_name=f"task3-{suffix}"),
    )
    decision = replace(
        decision_fixture(),
        decision_id=decision_id,
        request_id=request_id,
    )
    attempt = replace(attempt_fixture(child_started=False), decision_id=decision_id)
    intervention = replace(
        intervention_fixture(),
        intervention_id=intervention_id,
        request=request,
        decision=decision,
    )

    def connect() -> Any:
        return pyexasol.connect(
            dsn=os.environ["SSS_EXASOL_DSN"],
            user=os.environ["SSS_EXASOL_USER"],
            password=os.environ["SSS_EXASOL_PASSWORD"],
            schema=os.environ["SSS_EXASOL_SCHEMA"],
            autocommit=False,
        )

    first_connection = connect()
    first_closed = False
    first = ExasolOperationalRepository(first_connection)
    event_id: int | None = None
    try:
        first.record_decision(
            request,
            decision,
            evidence_as_of=NOW,
            evidence_attestation="c" * 64,
        )
        first.record_attempt(attempt)
        first.create_intervention(intervention)
        first.claim_idempotency(idempotency_key, "d" * 64, decision_id)
        first_connection.execute(
            "INSERT INTO APPROVAL_GRANTS (APPROVAL_ID, SCOPE_JSON, SIGNER, CREATED_AT, "
            "EXPIRES_AT, CONSUMED_AT, NONCE, REQUEST_ID, INTERVENTION_ID) VALUES "
            "({approval_id}, {scope_json}, {signer}, {created_at}, {expires_at}, NULL, "
            "{nonce}, {request_id}, {intervention_id})",
            {
                "approval_id": approval_id,
                "scope_json": "{}",
                "signer": "task3-live-test",
                "created_at": NOW.replace(tzinfo=None),
                "expires_at": (NOW + timedelta(hours=1)).replace(tzinfo=None),
                "nonce": f"task3-nonce-{suffix}",
                "request_id": request_id,
                "intervention_id": intervention_id,
            },
        )
        first_connection.commit()
        with pytest.raises(ApprovalNonceConflict):
            first.consume_approval_nonce(
                approval_id,
                f"task3-nonce-{suffix}",
                f"wrong-{request_id}",
                consumed_at=NOW,
                metadata={"source": "wrong-request"},
            )
        with pytest.raises(ApprovalNonceConflict):
            first.consume_approval_nonce(
                approval_id,
                f"task3-nonce-{suffix}",
                request_id,
                consumed_at=NOW + timedelta(hours=2),
                metadata={"source": "expired"},
            )
        first.consume_approval_nonce(
            approval_id,
            f"task3-nonce-{suffix}",
            request_id,
            consumed_at=NOW,
            metadata={"source": "task3-live-test"},
        )
        event_id = first.append_event(
            "install.blocked",
            {"decision_id": decision_id},
            occurred_at=NOW,
        ).event_id
        first_connection.close()
        first_closed = True

        second_connection = connect()
        second = ExasolOperationalRepository(second_connection)
        try:
            assert any(
                item.decision_id == decision_id and item.child_started is False
                for item in second.list_attempts(limit=1000)
            )
            assert any(
                item.intervention_id == intervention_id and item.package == request.package
                for item in second.list_interventions(pending_only=True, limit=1000)
            )
            claim = second.get_idempotency(idempotency_key)
            assert claim is not None
            assert claim.response_reference == decision_id
            assert second.events_after(after_id=event_id - 1, limit=1)[0].event_id == event_id
            consumed = second_connection.execute(
                "SELECT CONSUMED_REQUEST_ID FROM APPROVAL_GRANTS "
                "WHERE APPROVAL_ID={approval_id}",
                {"approval_id": approval_id},
            ).fetchall()
            assert consumed == [(request_id,)]
        finally:
            second_connection.execute(
                "DELETE FROM IDEMPOTENCY_CLAIMS WHERE IDEMPOTENCY_KEY={key}",
                {"key": idempotency_key},
            )
            second_connection.execute(
                "DELETE FROM INTERVENTIONS WHERE INTERVENTION_ID={intervention_id}",
                {"intervention_id": intervention_id},
            )
            second_connection.execute(
                "DELETE FROM INSTALL_ATTEMPTS WHERE DECISION_ID={decision_id}",
                {"decision_id": decision_id},
            )
            second_connection.execute(
                "DELETE FROM APPROVAL_GRANTS WHERE APPROVAL_ID={approval_id}",
                {"approval_id": approval_id},
            )
            second_connection.execute(
                "DELETE FROM EVENT_LOG WHERE EVENT_ID={event_id}",
                {"event_id": event_id},
            )
            second_connection.execute(
                "DELETE FROM POLICY_DECISIONS WHERE DECISION_ID={decision_id}",
                {"decision_id": decision_id},
            )
            second_connection.commit()
            second_connection.close()
    finally:
        if not first_closed:
            first_connection.close()


@pytest.mark.skipif(
    not os.getenv("SSS_EXASOL_DSN"),
    reason="requires an explicitly provisioned Exasol database",
)
def test_live_concurrent_attempt_and_intervention_replay() -> None:
    import pyexasol
    from sss_api.services.attempts import AttemptStore
    from sss_api.services.interventions import InterventionStore
    from sss_core.repositories.exasol import ExasolOperationalRepository

    suffix = uuid4().hex
    attempt_key = f"task3-race:{suffix}"
    attempt = replace(
        attempt_fixture(child_started=False), decision_id=f"race-decision-{suffix}"
    )
    base = intervention_fixture()
    decision = replace(
        base.decision,
        decision_id=f"race-intervention-{suffix}",
        request_id=f"race-request-{suffix}",
    )
    request = replace(base.request, request_id=decision.request_id)

    def connect() -> Any:
        return pyexasol.connect(
            dsn=os.environ["SSS_EXASOL_DSN"],
            user=os.environ["SSS_EXASOL_USER"],
            password=os.environ["SSS_EXASOL_PASSWORD"],
            schema=os.environ["SSS_EXASOL_SCHEMA"],
            autocommit=False,
        )

    class BarrierConnection:
        def __init__(self, connection: Any, marker: str, barrier: Barrier) -> None:
            self.connection = connection
            self.marker = marker
            self.barrier = barrier
            self.waited = False

        def execute(self, sql: str, query_params: dict[str, Any] | None = None) -> Any:
            normalized = " ".join(sql.upper().split())
            if not self.waited and self.marker in normalized:
                self.waited = True
                self.barrier.wait(timeout=10)
            return self.connection.execute(sql, query_params)

        def commit(self) -> None:
            self.connection.commit()

        def rollback(self) -> None:
            self.connection.rollback()

        def close(self) -> None:
            self.connection.close()

    attempt_barrier = Barrier(2)

    def record_attempt() -> InstallAttempt:
        connection = BarrierConnection(connect(), "SELECT ATTEMPT_ID", attempt_barrier)
        try:
            repository = ExasolOperationalRepository(connection)
            return AttemptStore(repository=repository).record(attempt_key, attempt)
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        attempt_futures = (executor.submit(record_attempt), executor.submit(record_attempt))
        attempt_results = tuple(future.result(timeout=20) for future in attempt_futures)
    assert attempt_results == (attempt, attempt)

    intervention_barrier = Barrier(2)

    def create_intervention() -> Intervention:
        connection = BarrierConnection(
            connect(), "SELECT INTERVENTION_ID", intervention_barrier
        )
        try:
            repository = ExasolOperationalRepository(connection)
            return InterventionStore(repository=repository).create(
                request,
                decision,
                evidence_labels=("race",),
                created_at=NOW,
            )
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        intervention_futures = (
            executor.submit(create_intervention),
            executor.submit(create_intervention),
        )
        intervention_results = tuple(
            future.result(timeout=20) for future in intervention_futures
        )
    assert intervention_results[0] == intervention_results[1]

    cleanup = connect()
    try:
        cleanup.execute(
            "DELETE FROM IDEMPOTENCY_CLAIMS WHERE IDEMPOTENCY_KEY={key}",
            {"key": attempt_key},
        )
        cleanup.execute(
            "DELETE FROM INSTALL_ATTEMPTS WHERE DECISION_ID={decision_id}",
            {"decision_id": attempt.decision_id},
        )
        cleanup.execute(
            "DELETE FROM INTERVENTIONS WHERE INTERVENTION_ID={intervention_id}",
            {"intervention_id": decision.decision_id},
        )
        cleanup.commit()
    finally:
        cleanup.close()
