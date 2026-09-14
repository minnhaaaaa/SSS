"""Authenticated install-attempt journal routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from sss_api.idempotency import require_idempotency_key
from sss_api.schemas.attempts import (
    InstallAttemptListResponse,
    InstallAttemptRequest,
    InstallAttemptResponse,
)
from sss_api.security import require_scope

router = APIRouter(
    prefix="/v1/install-attempts",
    tags=["attempts"],
)


@router.post(
    "",
    response_model=InstallAttemptResponse,
    status_code=201,
    dependencies=[Depends(require_scope("agent:check"))],
)
async def record(
    payload: InstallAttemptRequest,
    request: Request,
    idempotency_key: str = Depends(require_idempotency_key),
) -> InstallAttemptResponse:
    try:
        attempt = request.app.state.install_attempt_store.record(
            idempotency_key,
            payload.to_domain(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return InstallAttemptResponse.from_domain(attempt)


@router.get(
    "",
    response_model=InstallAttemptListResponse,
    dependencies=[Depends(require_scope("operator:intervene"))],
)
async def list_attempts(request: Request) -> InstallAttemptListResponse:
    return InstallAttemptListResponse(
        items=tuple(
            InstallAttemptResponse.from_domain(attempt)
            for attempt in request.app.state.install_attempt_store.list_all()
        )
    )
