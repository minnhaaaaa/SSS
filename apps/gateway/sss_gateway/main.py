"""Gateway process composition; policy routes are added after contracts freeze."""

from __future__ import annotations

from fastapi import FastAPI

from sss_gateway.config import GatewaySettings


def create_app(*, settings: GatewaySettings | None = None) -> FastAPI:
    resolved = settings or GatewaySettings.from_env()
    app = FastAPI(title="SSS Registry Gateway", version="0.1.0")
    app.state.settings = resolved

    @app.get("/health/live", tags=["health"])
    async def live() -> dict[str, object]:
        return {
            "status": "ok",
            "service": "sss-gateway",
            "configured_upstreams": sorted(resolved.upstreams),
        }

    return app
