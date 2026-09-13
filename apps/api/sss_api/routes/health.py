"""Process liveness and dependency readiness routes."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def live(request: Request) -> dict[str, str]:
    return {
        "status": "ok",
        "service": "sss-api",
        "environment": request.app.state.settings.environment,
    }


@router.get("/health/ready")
async def ready(request: Request) -> JSONResponse:
    report = await run_in_threadpool(request.app.state.readiness_service.check)
    return JSONResponse(
        status_code=200 if report.ready else 503,
        content={
            "status": "ready" if report.ready else "not_ready",
            "service": "sss-api",
            "policy": report.policy,
            "exasol": report.exasol,
        },
    )
