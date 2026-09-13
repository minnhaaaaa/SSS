"""FastAPI composition for the independently owned API boundary."""

from __future__ import annotations

from fastapi import FastAPI

from sss_api.config import ApiSettings
from sss_api.events import EventBroker
from sss_api.middleware.body_limit import RequestBodyLimitMiddleware
from sss_api.middleware.request_id import RequestIdMiddleware
from sss_api.routes import events, health


def create_app(
    *, settings: ApiSettings | None = None, event_broker: EventBroker | None = None
) -> FastAPI:
    resolved_settings = settings or ApiSettings.from_env()
    app = FastAPI(title="SSS API", version="0.1.0")
    app.state.settings = resolved_settings
    app.state.event_broker = event_broker or EventBroker(capacity=resolved_settings.sse_buffer_size)
    app.add_middleware(RequestBodyLimitMiddleware, max_bytes=resolved_settings.max_body_bytes)
    app.add_middleware(RequestIdMiddleware)
    app.include_router(health.router)
    app.include_router(events.router)
    return app


app = create_app()
