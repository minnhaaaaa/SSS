"""Authenticated operator intervention routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from sss_api.idempotency import require_idempotency_key
from sss_api.schemas.guard import InterventionListResponse, InterventionResponse
from sss_api.security import require_service_token

router = APIRouter(
    prefix="/v1/interventions",
    tags=["interventions"],
    dependencies=[Depends(require_service_token)],
)


@router.get("", response_model=InterventionListResponse)
async def list_pending(request: Request) -> InterventionListResponse:
    return InterventionListResponse(
        items=tuple(
            InterventionResponse.from_domain(item)
            for item in request.app.state.intervention_store.list_pending()
        )
    )


@router.get("/{intervention_id}", response_model=InterventionResponse)
async def detail(intervention_id: str, request: Request) -> InterventionResponse:
    try:
        item = request.app.state.intervention_store.get(intervention_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return InterventionResponse.from_domain(item)


@router.post(
    "/{intervention_id}/keep-blocked",
    response_model=InterventionResponse,
)
async def keep_blocked(
    intervention_id: str,
    request: Request,
    _idempotency_key: str = Depends(require_idempotency_key),
) -> InterventionResponse:
    try:
        item = request.app.state.intervention_store.keep_blocked(intervention_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return InterventionResponse.from_domain(item)
