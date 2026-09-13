"""Authenticated local-demo state routes."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict

from sss_api.idempotency import require_idempotency_key
from sss_api.security import require_scope
from sss_api.services.demo import DemoStatus

router = APIRouter(
    prefix="/v1/demo",
    tags=["demo"],
    dependencies=[Depends(require_scope("operator:intervene"))],
)


class DemoStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    state: str
    canary_count: int
    protected_child_started: bool | None
    protected_exit_code: int | None

    @classmethod
    def from_domain(cls, value: DemoStatus) -> DemoStatusResponse:
        return cls(
            state=value.state.value,
            canary_count=value.canary_count,
            protected_child_started=value.protected_child_started,
            protected_exit_code=value.protected_exit_code,
        )


class UnprotectedResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    canary_before: int
    canary_after: int


class ProtectedResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    exit_code: int
    child_process_started: bool
    canary_after: int


def _apply(action: Callable[[], DemoStatus]) -> DemoStatusResponse:
    try:
        return DemoStatusResponse.from_domain(action())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/status", response_model=DemoStatusResponse)
async def demo_status(request: Request) -> DemoStatusResponse:
    return DemoStatusResponse.from_domain(request.app.state.demo_controller.status())


@router.post("/reset", response_model=DemoStatusResponse)
async def reset(
    request: Request,
    _key: str = Depends(require_idempotency_key),
) -> DemoStatusResponse:
    return _apply(request.app.state.demo_controller.reset)


@router.post("/replay", response_model=DemoStatusResponse)
async def replay(
    request: Request,
    _key: str = Depends(require_idempotency_key),
) -> DemoStatusResponse:
    return _apply(request.app.state.demo_controller.replay)


@router.post("/register", response_model=DemoStatusResponse)
async def register(
    request: Request,
    _key: str = Depends(require_idempotency_key),
) -> DemoStatusResponse:
    return _apply(request.app.state.demo_controller.register)


@router.post("/unprotected", response_model=DemoStatusResponse)
async def unprotected(
    payload: UnprotectedResult,
    request: Request,
    _key: str = Depends(require_idempotency_key),
) -> DemoStatusResponse:
    return _apply(
        lambda: request.app.state.demo_controller.record_unprotected(
            canary_before=payload.canary_before,
            canary_after=payload.canary_after,
        )
    )


@router.post("/protected", response_model=DemoStatusResponse)
async def protected(
    payload: ProtectedResult,
    request: Request,
    _key: str = Depends(require_idempotency_key),
) -> DemoStatusResponse:
    return _apply(
        lambda: request.app.state.demo_controller.record_protected(
            exit_code=payload.exit_code,
            child_process_started=payload.child_process_started,
            canary_after=payload.canary_after,
        )
    )
