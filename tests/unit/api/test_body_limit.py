from __future__ import annotations

from collections.abc import Awaitable, Callable

import pytest
from sss_api.middleware.body_limit import RequestBodyLimitMiddleware
from starlette.types import Message, Scope


@pytest.mark.asyncio
async def test_chunked_oversized_body_returns_413_when_downstream_disconnects() -> None:
    async def downstream(
        scope: Scope,
        receive: Callable[[], Awaitable[Message]],
        send: Callable[[Message], Awaitable[None]],
    ) -> None:
        del scope, send
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                raise RuntimeError("client disconnected")
            if not message.get("more_body", False):
                return

    incoming = iter(
        [
            {"type": "http.request", "body": b"1234", "more_body": True},
            {"type": "http.request", "body": b"5678", "more_body": False},
        ]
    )
    outgoing: list[Message] = []

    async def receive() -> Message:
        return next(incoming)  # type: ignore[return-value]

    async def send(message: Message) -> None:
        outgoing.append(message)

    middleware = RequestBodyLimitMiddleware(downstream, max_bytes=6)
    await middleware(
        {"type": "http", "method": "POST", "path": "/", "headers": []},
        receive,
        send,
    )

    assert outgoing[0]["type"] == "http.response.start"
    assert outgoing[0]["status"] == 413
