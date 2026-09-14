"""Collector-scoped observation ingestion."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sss_core.repositories.operations import IdempotencyConflict

from sss_api.idempotency import require_idempotency_key
from sss_api.schemas.observations import (
    ClientObservationRequest,
    ModelObservationRequest,
    ObservationAccepted,
    PublicObservationRequest,
    RegistryObservationRequest,
)
from sss_api.security import require_scope

router = APIRouter(
    prefix="/v1/observations",
    tags=["observations"],
    dependencies=[Depends(require_scope("collector:write"))],
)


def _record(kind: str, payload: object, request: Request, key: str) -> ObservationAccepted:
    try:
        identifier = request.app.state.observation_repository.record(kind, payload, key)
    except IdempotencyConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return ObservationAccepted(observation_id=identifier)


@router.post("/model", response_model=ObservationAccepted, status_code=status.HTTP_202_ACCEPTED)
async def model(
    payload: ModelObservationRequest,
    request: Request,
    key: str = Depends(require_idempotency_key),
) -> ObservationAccepted:
    return _record("model", payload, request, key)


@router.post("/client", response_model=ObservationAccepted, status_code=status.HTTP_202_ACCEPTED)
async def client(
    payload: ClientObservationRequest,
    request: Request,
    key: str = Depends(require_idempotency_key),
) -> ObservationAccepted:
    return _record("client", payload, request, key)


@router.post("/public", response_model=ObservationAccepted, status_code=status.HTTP_202_ACCEPTED)
async def public(
    payload: PublicObservationRequest,
    request: Request,
    key: str = Depends(require_idempotency_key),
) -> ObservationAccepted:
    return _record("public", payload, request, key)


@router.post("/registry", response_model=ObservationAccepted, status_code=status.HTTP_202_ACCEPTED)
async def registry(
    payload: RegistryObservationRequest,
    request: Request,
    key: str = Depends(require_idempotency_key),
) -> ObservationAccepted:
    return _record("registry", payload, request, key)
