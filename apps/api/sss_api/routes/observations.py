"""Authenticated evidence-ingestion endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from sss_api.idempotency import require_idempotency_key
from sss_api.schemas.observations import (
    ClientObservation,
    ModelObservation,
    ObservationReceipt,
    PublicObservation,
)
from sss_api.security import require_service_token

router = APIRouter(
    prefix="/v1/observations",
    tags=["observations"],
    dependencies=[Depends(require_service_token)],
)


async def _record(
    payload: ModelObservation | PublicObservation | ClientObservation,
    request: Request,
    idempotency_key: str,
) -> ObservationReceipt:
    try:
        stored = await request.app.state.observation_store.record(idempotency_key, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await request.app.state.event_broker.publish(
        "evidence.observed",
        {
            "observation_id": stored.observation_id,
            "ecosystem": stored.package.ecosystem.value,
            "canonical_name": stored.package.canonical_name,
            "provenance": stored.provenance,
        },
    )
    return ObservationReceipt(
        observation_id=stored.observation_id,
        accepted=True,
        observed_at=stored.observed_at,
    )


@router.post("/model", response_model=ObservationReceipt, status_code=201)
async def record_model(
    payload: ModelObservation,
    request: Request,
    idempotency_key: str = Depends(require_idempotency_key),
) -> ObservationReceipt:
    return await _record(payload, request, idempotency_key)


@router.post("/public", response_model=ObservationReceipt, status_code=201)
async def record_public(
    payload: PublicObservation,
    request: Request,
    idempotency_key: str = Depends(require_idempotency_key),
) -> ObservationReceipt:
    return await _record(payload, request, idempotency_key)


@router.post("/client", response_model=ObservationReceipt, status_code=201)
async def record_client(
    payload: ClientObservation,
    request: Request,
    idempotency_key: str = Depends(require_idempotency_key),
) -> ObservationReceipt:
    return await _record(payload, request, idempotency_key)
