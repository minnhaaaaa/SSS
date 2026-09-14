"""Liveness and dependency-aware readiness routes."""

from fastapi import APIRouter, HTTPException, Request, status
from sss_core import POLICY_VERSION, RuntimeMode

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def live(request: Request) -> dict[str, str]:
    return {
        "status": "ok",
        "service": "sss-api",
        "environment": request.app.state.settings.environment,
    }


@router.get("/health/ready")
async def ready(request: Request) -> dict[str, str]:
    if request.app.state.runtime_mode is not RuntimeMode.PRODUCTION:
        return {
            "status": "ready",
            "exasol": "not-required",
            "schema_version": "not-required",
            "policy_version": request.app.state.settings.policy_version,
        }
    try:
        connection = request.app.state.exasol_connection
        readiness = request.app.state.schema_readiness
        connection.execute("SELECT 1")
        if readiness is None or not readiness.ready:
            raise RuntimeError("schema is not ready")
        if request.app.state.settings.policy_version != POLICY_VERSION:
            raise RuntimeError("policy version is not ready")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="production dependencies are not ready",
        ) from exc
    return {
        "status": "ready",
        "exasol": "ready",
        "schema_version": readiness.current_version or "unknown",
        "policy_version": request.app.state.settings.policy_version,
    }
