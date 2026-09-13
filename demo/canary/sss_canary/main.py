"""Authenticated local-only canary API used to prove execution or non-execution."""

from __future__ import annotations

from secrets import compare_digest

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict

from sss_canary.config import CanarySettings
from sss_canary.repository import CanaryRepository


class CanaryEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    marker: str


def create_app(
    *,
    settings: CanarySettings | None = None,
    repository: CanaryRepository | None = None,
) -> FastAPI:
    resolved_settings = settings or CanarySettings.from_env()
    resolved_repository = repository or CanaryRepository(resolved_settings.database_path)
    resolved_repository.initialize()
    app = FastAPI(title="SSS Demo Canary", version="0.1.0")

    async def authorize(authorization: str | None = Header(default=None)) -> None:
        scheme, separator, credential = (authorization or "").partition(" ")
        if not (
            separator
            and scheme.casefold() == "bearer"
            and compare_digest(credential, resolved_settings.token)
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing canary token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    @app.get("/health/live", tags=["health"])
    async def live() -> dict[str, str]:
        return {"status": "ok", "service": "sss-canary"}

    @app.get("/v1/count", dependencies=[Depends(authorize)])
    async def count() -> dict[str, int]:
        return {"count": resolved_repository.count()}

    @app.post("/v1/events", dependencies=[Depends(authorize)], status_code=201)
    async def record_event(payload: CanaryEventRequest) -> dict[str, object]:
        if not compare_digest(payload.marker, resolved_settings.marker):
            raise HTTPException(status_code=422, detail="Unexpected canary marker")
        event = resolved_repository.record(payload.marker)
        return {"event_id": event.event_id, "occurred_at": event.occurred_at}

    @app.post("/v1/reset", dependencies=[Depends(authorize)])
    async def reset() -> dict[str, int]:
        resolved_repository.reset()
        return {"count": 0}

    return app
