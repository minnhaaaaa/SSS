"""Idempotent install-attempt journal."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from threading import RLock

from sss_core import Decision
from sss_core.repositories.operations import InstallAttempt, OperationalRepository

from sss_api.idempotency import idempotency_request_hash

__all__ = ["AttemptStore", "InstallAttempt", "new_attempt"]


class AttemptStore:
    def __init__(self, repository: OperationalRepository | None = None) -> None:
        self._by_key: dict[str, InstallAttempt] = {}
        self._lock = RLock()
        self._repository = repository

    @staticmethod
    def _request_hash(attempt: InstallAttempt) -> str:
        return idempotency_request_hash(
            {
                "decision_id": attempt.decision_id,
                "manager": attempt.manager,
                "arguments": list(attempt.arguments),
                "agent_family": attempt.agent_family,
                "project_id": attempt.project_id,
                "decision": attempt.decision.value,
                "child_started": attempt.child_started,
            }
        )

    def record(self, idempotency_key: str, attempt: InstallAttempt) -> InstallAttempt:
        if self._repository is not None:
            request_hash = self._request_hash(attempt)
            attempt_id = idempotency_request_hash(
                {
                    "operation": "install-attempt",
                    "idempotency_key": idempotency_key,
                    "request_hash": request_hash,
                }
            )
            claim = self._repository.claim_idempotency(
                idempotency_key,
                request_hash,
                attempt_id,
            )
            durable_attempt = self._repository.get_attempt(claim.response_reference)
            if durable_attempt is not None:
                return durable_attempt
            return self._repository.record_attempt(
                attempt,
                attempt_id=claim.response_reference,
            )
        with self._lock:
            existing_attempt = self._by_key.get(idempotency_key)
            if existing_attempt is not None:
                if replace(existing_attempt, attempted_at=attempt.attempted_at) != attempt:
                    raise ValueError("idempotency key was already used for another attempt")
                return existing_attempt
            self._by_key[idempotency_key] = attempt
            return attempt

    def list_all(self) -> tuple[InstallAttempt, ...]:
        if self._repository is not None:
            return self._repository.list_attempts(limit=1000)
        with self._lock:
            return tuple(self._by_key.values())


def new_attempt(
    *,
    decision_id: str,
    manager: str,
    arguments: tuple[str, ...],
    agent_family: str,
    project_id: str,
    decision: Decision,
    child_started: bool,
) -> InstallAttempt:
    return InstallAttempt(
        decision_id=decision_id,
        manager=manager,
        arguments=arguments,
        agent_family=agent_family,
        project_id=project_id,
        decision=decision,
        child_started=child_started,
        attempted_at=datetime.now(UTC),
    )
