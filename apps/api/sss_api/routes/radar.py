"""Private cursor-paginated Radar reads."""

from __future__ import annotations

import base64
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict

from sss_api.security import require_scope

router = APIRouter(
    prefix="/v1/radar",
    tags=["radar"],
    dependencies=[Depends(require_scope("radar:read"))],
)


class RadarItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    ecosystem: str
    registry_origin: str
    canonical_name: str
    status: str
    first_absence_at: datetime | None
    first_registration_at: datetime | None
    synthetic: bool
    verified_model_recommendations: int
    model_configurations: int
    protected_agent_attempts: int
    public_failed_references: int
    observation_days: int
    has_explicit_context: bool


class RadarPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    items: tuple[RadarItem, ...]
    next_cursor: str | None


def _decode_cursor(value: str | None) -> tuple[datetime, str] | None:
    if value is None:
        return None
    try:
        padding = "=" * (-len(value) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(value + padding))
        if not isinstance(decoded, list) or len(decoded) != 2:
            raise ValueError
        return datetime.fromisoformat(str(decoded[0])), str(decoded[1])
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid cursor"
        ) from exc


def _encode_cursor(value: tuple[datetime, str] | None) -> str | None:
    if value is None:
        return None
    payload = json.dumps([value[0].isoformat(), value[1]], separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


@router.get("", response_model=RadarPage)
async def list_radar(
    request: Request,
    limit: int = Query(default=100, ge=1, le=200),
    cursor: str | None = Query(default=None, max_length=2048),
) -> RadarPage:
    rows, next_value = request.app.state.radar_repository.list_private_page(
        limit=limit, cursor=_decode_cursor(cursor)
    )
    return RadarPage(
        items=tuple(RadarItem.model_validate(row) for row in rows),
        next_cursor=_encode_cursor(next_value),
    )
