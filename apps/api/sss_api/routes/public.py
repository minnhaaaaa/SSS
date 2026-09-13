"""Read-only browser views backed by persisted or current runtime evidence."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import suppress
from typing import Any, cast

from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from sss_api.events import ServerEvent

router = APIRouter(prefix="/v1/public", tags=["public"])


@router.get("/overview")
async def overview(request: Request) -> dict[str, Any]:
    service = request.app.state.control_room_service
    return cast(dict[str, Any], await run_in_threadpool(service.overview))


@router.get("/packages")
async def packages(request: Request) -> list[dict[str, Any]]:
    service = request.app.state.control_room_service
    return cast(list[dict[str, Any]], await run_in_threadpool(service.packages))


@router.get("/packages/{name:path}")
async def package_detail(name: str, request: Request) -> dict[str, Any]:
    service = request.app.state.control_room_service
    found = await run_in_threadpool(service.package, name)
    if found is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="package not found")
    return cast(dict[str, Any], found)


@router.get("/evidence/{name:path}")
async def evidence(name: str, request: Request) -> list[dict[str, Any]]:
    service = request.app.state.control_room_service
    found = await run_in_threadpool(service.package, name)
    if found is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="package not found")
    return cast(list[dict[str, Any]], await run_in_threadpool(service.evidence, name))


@router.get("/decisions")
async def decisions(request: Request) -> list[dict[str, Any]]:
    service = request.app.state.control_room_service
    return cast(list[dict[str, Any]], await run_in_threadpool(service.decisions))


@router.get("/coverage")
async def coverage(request: Request) -> dict[str, Any]:
    service = request.app.state.control_room_service
    return cast(dict[str, Any], await run_in_threadpool(service.coverage))


@router.get("/events")
async def events(
    request: Request,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
) -> StreamingResponse:
    try:
        start_id = max(int(last_event_id or "0"), 0)
    except ValueError:
        start_id = 0
    return StreamingResponse(
        _public_event_stream(request, start_id=start_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _public_event_stream(request: Request, *, start_id: int) -> AsyncIterator[str]:
    broker = request.app.state.event_broker
    stream = broker.stream(after_id=start_id).__aiter__()
    pending: asyncio.Task[ServerEvent] | None = None
    try:
        while True:
            if await request.is_disconnected():
                return
            if pending is None:
                pending = asyncio.create_task(stream.__anext__())
            completed, _ = await asyncio.wait(
                {pending}, timeout=request.app.state.settings.sse_heartbeat_seconds
            )
            if not completed:
                yield ": heartbeat\n\n"
                continue
            event = pending.result()
            pending = None
            payload = json.dumps({"occurred_at": event.occurred_at.isoformat()})
            yield f"id: {event.event_id}\nevent: {event.event_type}\ndata: {payload}\n\n"
    finally:
        if pending is not None and not pending.done():
            pending.cancel()
            with suppress(asyncio.CancelledError):
                await pending
