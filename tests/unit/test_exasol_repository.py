from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from sss_core.domain import CandidateStatus, Ecosystem, PackageIdentity, RegistryStatus
from sss_core.repositories.exasol import ExasolEvidenceRepository, RegistryEvidenceRecord


class RecordingConnection:
    def __init__(self, *, fail_second: bool = False) -> None:
        self.calls: list[tuple[str, dict[str, Any] | None]] = []
        self.commits = 0
        self.rollbacks = 0
        self.fail_second = fail_second

    def execute(self, sql: str, query_params: dict[str, Any] | None = None) -> list[Any]:
        self.calls.append((sql, query_params))
        if self.fail_second and len(self.calls) == 2:
            raise RuntimeError("transition write failed")
        return []

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def _record() -> RegistryEvidenceRecord:
    return RegistryEvidenceRecord(
        check_id="check-1",
        package=PackageIdentity(Ecosystem.NPM, "https://registry.npmjs.org", "demo"),
        endpoint="https://registry.npmjs.org/demo",
        status=RegistryStatus.REGISTERED,
        http_status=200,
        checked_at=datetime(2026, 9, 7, tzinfo=UTC),
        response_sha256="a" * 64,
        error_class=None,
    )


def test_evidence_and_transition_write_is_atomic_and_parameterized() -> None:
    connection = RecordingConnection()
    repository = ExasolEvidenceRepository(connection)

    repository.store_evidence_and_transition(
        _record(), CandidateStatus.REGISTERED_AFTER_ABSENCE
    )

    assert connection.commits == 1
    assert connection.rollbacks == 0
    assert len(connection.calls) == 2
    assert all("demo" not in sql for sql, _ in connection.calls)
    assert all(params is not None for _, params in connection.calls)


def test_failed_transition_rolls_back_evidence_write() -> None:
    connection = RecordingConnection(fail_second=True)
    repository = ExasolEvidenceRepository(connection)

    with pytest.raises(RuntimeError, match="transition write failed"):
        repository.store_evidence_and_transition(
            _record(), CandidateStatus.REGISTERED_AFTER_ABSENCE
        )

    assert connection.commits == 0
    assert connection.rollbacks == 1
