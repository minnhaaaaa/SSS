"""Bounded in-process event broker with resumable event identifiers."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any


@dataclass(frozen=True, slots=True)
class ServerEvent:
    event_id: int
    event_type: str
    payload: Mapping[str, Any]
    occurred_at: datetime


class EventBroker:
    def __init__(self, *, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self._events: deque[ServerEvent] = deque(maxlen=capacity)
        self._condition = asyncio.Condition()
        self._next_id = 1

    async def publish(self, event_type: str, payload: Mapping[str, Any]) -> ServerEvent:
        if not event_type or any(character.isspace() for character in event_type):
            raise ValueError("event_type must be a non-empty token")
        async with self._condition:
            event = ServerEvent(
                event_id=self._next_id,
                event_type=event_type,
                payload=MappingProxyType(dict(payload)),
                occurred_at=datetime.now(UTC),
            )
            self._next_id += 1
            self._events.append(event)
            self._condition.notify_all()
            return event

    async def stream(self, *, after_id: int = 0) -> AsyncIterator[ServerEvent]:
        cursor = max(after_id, 0)
        while True:
            async with self._condition:
                ready = [event for event in self._events if event.event_id > cursor]
                if not ready:
                    await self._condition.wait()
                    continue
            for event in ready:
                cursor = event.event_id
                yield event

    def snapshot(self, *, after_id: int = 0) -> tuple[ServerEvent, ...]:
        return tuple(event for event in self._events if event.event_id > after_id)
