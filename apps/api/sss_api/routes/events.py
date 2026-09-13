"""Authenticated Server-Sent Events endpoint."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import suppress

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse

from sss_api.events import ServerEvent
from sss_api.security import require_service_token

router = APIRouter(prefix="/v1", tags=["events"])


@router.get("/events", dependencies=[Depends(require_service_token)])
async def events(
    request: Request,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
) -> StreamingResponse:
    start_id = _parse_last_event_id(last_event_id)
    return StreamingResponse(
        _event_stream(request, start_id=start_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _parse_last_event_id(value: str | None) -> int:
    if value is None:
        return 0
    try:
        return max(int(value), 0)
    except ValueError:
        return 0


async def _event_stream(request: Request, *, start_id: int) -> AsyncIterator[str]:
    broker = request.app.state.event_broker
    heartbeat = request.app.state.settings.sse_heartbeat_seconds
    stream = broker.stream(after_id=start_id).__aiter__()
    pending_event: asyncio.Task[ServerEvent] | None = None
    try:
        while True:
            if await request.is_disconnected():
                return
            if pending_event is None:
                pending_event = asyncio.create_task(stream.__anext__())
            completed, _ = await asyncio.wait({pending_event}, timeout=heartbeat)
            if not completed:
                yield ": heartbeat\n\n"
                continue
            event = pending_event.result()
            pending_event = None
            yield _format_event(event)
    finally:
        if pending_event is not None and not pending_event.done():
            pending_event.cancel()
            with suppress(asyncio.CancelledError):
                await pending_event


def _format_event(event: ServerEvent) -> str:
    payload = {
        **event.payload,
        "occurred_at": event.occurred_at.isoformat(),
    }
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    return f"id: {event.event_id}\nevent: {event.event_type}\ndata: {encoded}\n\n"
