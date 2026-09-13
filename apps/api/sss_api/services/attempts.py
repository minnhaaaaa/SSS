"""Idempotent install-attempt journal."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from threading import RLock

from sss_core import Decision


@dataclass(frozen=True, slots=True)
class InstallAttempt:
    decision_id: str
    manager: str
    arguments: tuple[str, ...]
    agent_family: str
    project_id: str
    decision: Decision
    child_started: bool
    attempted_at: datetime


class AttemptStore:
    def __init__(self) -> None:
        self._by_key: dict[str, InstallAttempt] = {}
        self._lock = RLock()

    def record(self, idempotency_key: str, attempt: InstallAttempt) -> InstallAttempt:
        with self._lock:
            existing = self._by_key.get(idempotency_key)
            if existing is not None:
                if replace(existing, attempted_at=attempt.attempted_at) != attempt:
                    raise ValueError("idempotency key was already used for another attempt")
                return existing
            self._by_key[idempotency_key] = attempt
            return attempt

    def list_all(self) -> tuple[InstallAttempt, ...]:
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
