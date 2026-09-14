from __future__ import annotations

import pytest
from sss_api.events import EventBroker
from sss_api.routes.events import _event_stream
from sss_api.routes.public import _public_event_stream


@pytest.mark.asyncio
async def test_event_broker_assigns_ids_and_resumes_after_cursor() -> None:
    broker = EventBroker(capacity=4)
    first = await broker.publish("observation.completed", {"value": 1})
    second = await broker.publish("install.blocked", {"value": 2})

    assert first.event_id == 1
    assert second.event_id == 2
    assert broker.snapshot(after_id=1) == (second,)


@pytest.mark.asyncio
async def test_event_broker_discards_oldest_items_at_capacity() -> None:
    broker = EventBroker(capacity=2)
    await broker.publish("first", {})
    second = await broker.publish("second", {})
    third = await broker.publish("third", {})

    assert broker.snapshot() == (second, third)


@pytest.mark.asyncio
async def test_sse_heartbeat_does_not_cancel_pending_event_wait() -> None:
    broker = EventBroker(capacity=2)

    class Settings:
        sse_heartbeat_seconds = 0.01

    class State:
        event_broker = broker
        settings = Settings()

    class App:
        state = State()

    class Request:
        app = App()

        async def is_disconnected(self) -> bool:
            return False

    stream = _event_stream(Request(), start_id=0)  # type: ignore[arg-type]
    assert await anext(stream) == ": heartbeat\n\n"

    event = await broker.publish("install.blocked", {"decision": "block"})
    delivered = await anext(stream)
    await stream.aclose()

    assert f"id: {event.event_id}" in delivered
    assert "event: install.blocked" in delivered


@pytest.mark.asyncio
async def test_public_sse_redacts_private_event_payload() -> None:
    broker = EventBroker(capacity=2)

    class Settings:
        sse_heartbeat_seconds = 0.01

    class State:
        event_broker = broker
        settings = Settings()

    class App:
        state = State()

    class Request:
        app = App()

        async def is_disconnected(self) -> bool:
            return False

    stream = _public_event_stream(Request(), start_id=0)  # type: ignore[arg-type]
    await broker.publish("install.blocked", {"private_package": "must-not-leak"})
    delivered = await anext(stream)
    await stream.aclose()

    assert "event: install.blocked" in delivered
    assert "must-not-leak" not in delivered
