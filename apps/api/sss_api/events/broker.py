"""Bounded in-process event broker with resumable event identifiers."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import AsyncIterator, Mapping
from contextlib import suppress
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from sss_core.repositories.operations import OperationalEvent, OperationalRepository

ServerEvent = OperationalEvent


class EventBroker:
    def __init__(
        self,
        *,
        capacity: int,
        repository: OperationalRepository | None = None,
        poll_interval: float = 0.25,
    ) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        if poll_interval <= 0:
            raise ValueError("poll_interval must be positive")
        self._events: deque[ServerEvent] = deque(maxlen=capacity)
        self._condition = asyncio.Condition()
        self._next_id = 1
        self._repository = repository
        self._poll_interval = poll_interval

    async def publish(self, event_type: str, payload: Mapping[str, Any]) -> ServerEvent:
        if not event_type or any(character.isspace() for character in event_type):
            raise ValueError("event_type must be a non-empty token")
        async with self._condition:
            if self._repository is None:
                event = ServerEvent(
                    event_id=self._next_id,
                    event_type=event_type,
                    payload=MappingProxyType(dict(payload)),
                    occurred_at=datetime.now(UTC),
                )
                self._next_id += 1
                self._events.append(event)
            else:
                event = self._repository.append_event(
                    event_type,
                    payload,
                    occurred_at=datetime.now(UTC),
                )
            self._condition.notify_all()
            return event

    async def stream(self, *, after_id: int = 0) -> AsyncIterator[ServerEvent]:
        cursor = max(after_id, 0)
        while True:
            if self._repository is not None:
                durable_ready = self._repository.events_after(
                    after_id=cursor,
                    limit=min(self._events.maxlen or 1000, 1000),
                )
                if not durable_ready:
                    async with self._condition:
                        with suppress(TimeoutError):
                            await asyncio.wait_for(
                                self._condition.wait(), timeout=self._poll_interval
                            )
                    continue
                for event in durable_ready:
                    cursor = event.event_id
                    yield event
                continue
            async with self._condition:
                ready = [event for event in self._events if event.event_id > cursor]
                if not ready:
                    await self._condition.wait()
                    continue
            for event in ready:
                cursor = event.event_id
                yield event

    def snapshot(self, *, after_id: int = 0) -> tuple[ServerEvent, ...]:
        if self._repository is not None:
            return self._repository.events_after(
                after_id=max(after_id, 0),
                limit=min(self._events.maxlen or 1000, 1000),
            )
        return tuple(event for event in self._events if event.event_id > after_id)
