"""Authenticated exact-scope approval routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from sss_api.idempotency import require_idempotency_key
from sss_api.schemas.approvals import (
    ApprovalConsumeRequest,
    ApprovalConsumeResponse,
    ApprovalCreateRequest,
    ApprovalCreateResponse,
)
from sss_api.security import require_service_token
from sss_api.services.approvals import ApprovalError

router = APIRouter(
    prefix="/v1/approvals",
    tags=["approvals"],
    dependencies=[Depends(require_service_token)],
)


def _service(request: Request):  # type: ignore[no-untyped-def]
    service = request.app.state.approval_service
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="approval signing is not configured",
        )
    return service


@router.post("", response_model=ApprovalCreateResponse, status_code=201)
async def create(
    payload: ApprovalCreateRequest,
    request: Request,
    _idempotency_key: str = Depends(require_idempotency_key),
) -> ApprovalCreateResponse:
    try:
        intervention = request.app.state.intervention_store.get(payload.intervention_id)
        grant = _service(request).issue(
            intervention_id=intervention.intervention_id,
            request=intervention.request,
            scope=payload.claims.to_scope(),
        )
        request.app.state.intervention_store.resolve_approved(
            intervention.intervention_id,
            grant.approval_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ApprovalError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return ApprovalCreateResponse.from_domain(grant)


@router.post("/consume", response_model=ApprovalConsumeResponse)
async def consume(
    payload: ApprovalConsumeRequest,
    request: Request,
    _idempotency_key: str = Depends(require_idempotency_key),
) -> ApprovalConsumeResponse:
    try:
        grant = _service(request).consume(
            token=payload.token,
            request_id=payload.request_id,
            expected_nonce=payload.expected_nonce,
        )
    except ApprovalError as exc:
        message = str(exc)
        code = status.HTTP_403_FORBIDDEN if "signature" in message or "invalid" in message else 409
        raise HTTPException(status_code=code, detail=message) from exc
    return ApprovalConsumeResponse(
        approval_id=grant.approval_id,
        consumed=True,
        remaining_uses=0,
    )
