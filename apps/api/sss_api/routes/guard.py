"""Authenticated Guard assessment routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from sss_api.idempotency import require_idempotency_key
from sss_api.schemas.guard import GuardCheckRequest, GuardCheckResponse
from sss_api.security import require_scope

router = APIRouter(prefix="/v1", tags=["guard"])


@router.post(
    "/check",
    response_model=GuardCheckResponse,
    dependencies=[Depends(require_scope("agent:check"))],
)
async def check(
    payload: GuardCheckRequest,
    request: Request,
    idempotency_key: str = Depends(require_idempotency_key),
) -> GuardCheckResponse:
    try:
        assessment = await request.app.state.guard_service.check(
            payload.to_domain(),
            idempotency_key=idempotency_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return GuardCheckResponse.from_assessment(assessment)
