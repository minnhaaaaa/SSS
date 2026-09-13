"""Registry gateway composition."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from sss_gateway.config import GatewaySettings
from sss_gateway.proxy import router as registry_router
from sss_gateway.upstream import RegistryUpstreamClient


def create_app(
    *,
    settings: GatewaySettings | None = None,
    upstream_client: RegistryUpstreamClient | None = None,
) -> FastAPI:
    resolved = settings or GatewaySettings.from_env()
    client = upstream_client or RegistryUpstreamClient(resolved)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        await client.close()

    app = FastAPI(title="SSS Registry Gateway", version="0.1.0", lifespan=lifespan)
    app.state.settings = resolved
    app.state.upstream_client = client
    app.include_router(registry_router)

    @app.get("/health/live", tags=["health"])
    async def live() -> dict[str, object]:
        return {
            "status": "ok",
            "service": "sss-gateway",
            "configured_upstreams": sorted(resolved.upstreams),
        }

    return app
