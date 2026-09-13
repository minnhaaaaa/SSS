"""Deterministic state controller for the narrated demo sequence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from threading import RLock
from typing import Protocol


class DemoRepository(Protocol):
    def reset(self) -> None: ...

    def replay(self) -> None: ...


class NoopDemoRepository:
    def reset(self) -> None:
        return None

    def replay(self) -> None:
        return None


class DemoState(StrEnum):
    READY = "ready"
    REPLAYED = "replayed"
    REGISTERED = "registered"
    UNPROTECTED = "unprotected"
    PROTECTED_BLOCKED = "protected_blocked"


@dataclass(frozen=True, slots=True)
class DemoStatus:
    state: DemoState
    canary_count: int
    protected_child_started: bool | None
    protected_exit_code: int | None


class DemoController:
    def __init__(self, *, repository: DemoRepository) -> None:
        self._repository = repository
        self._state = DemoState.READY
        self._canary_count = 0
        self._protected_child_started: bool | None = None
        self._protected_exit_code: int | None = None
        self._lock = RLock()

    def status(self) -> DemoStatus:
        with self._lock:
            return self._snapshot()

    def reset(self) -> DemoStatus:
        with self._lock:
            self._repository.reset()
            self._state = DemoState.READY
            self._canary_count = 0
            self._protected_child_started = None
            self._protected_exit_code = None
            return self._snapshot()

    def replay(self) -> DemoStatus:
        with self._lock:
            if self._state is DemoState.REPLAYED:
                return self._snapshot()
            if self._state is not DemoState.READY:
                raise ValueError("reset before replay evidence")
            self._repository.replay()
            self._state = DemoState.REPLAYED
            return self._snapshot()

    def register(self) -> DemoStatus:
        with self._lock:
            if self._state is DemoState.REGISTERED:
                return self._snapshot()
            if self._state is not DemoState.REPLAYED:
                raise ValueError("replay evidence before registration")
            self._state = DemoState.REGISTERED
            return self._snapshot()

    def record_unprotected(self, *, canary_before: int, canary_after: int) -> DemoStatus:
        with self._lock:
            if self._state is DemoState.UNPROTECTED:
                return self._snapshot()
            if self._state is not DemoState.REGISTERED:
                raise ValueError("register the fixture before the unprotected run")
            if canary_before != 0 or canary_after != 1:
                raise ValueError("unprotected run must increment the reset canary from zero to one")
            self._canary_count = canary_after
            self._state = DemoState.UNPROTECTED
            return self._snapshot()

    def record_protected(
        self,
        *,
        exit_code: int,
        child_process_started: bool,
        canary_after: int,
    ) -> DemoStatus:
        with self._lock:
            if self._state is DemoState.PROTECTED_BLOCKED:
                return self._snapshot()
            if self._state is not DemoState.UNPROTECTED:
                raise ValueError("run the unprotected control before the protected agent")
            if exit_code != 23 or child_process_started or canary_after != self._canary_count:
                raise ValueError(
                    "protected completion requires exit 23 and unchanged non-execution"
                )
            self._protected_exit_code = exit_code
            self._protected_child_started = child_process_started
            self._state = DemoState.PROTECTED_BLOCKED
            return self._snapshot()

    def _snapshot(self) -> DemoStatus:
        return DemoStatus(
            state=self._state,
            canary_count=self._canary_count,
            protected_child_started=self._protected_child_started,
            protected_exit_code=self._protected_exit_code,
        )
