"""Private cursor-paginated Radar reads."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict

from sss_api.security import require_scope

router = APIRouter(
    prefix="/v1/radar",
    tags=["radar"],
    dependencies=[Depends(require_scope("radar:read"))],
)
private_router = APIRouter(
    prefix="/v1",
    tags=["private-intelligence"],
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
    data_as_of: datetime


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
        data_as_of=_data_as_of(request),
    )


def _data_as_of(request: Request) -> datetime:
    repository = request.app.state.radar_repository
    method = getattr(repository, "data_as_of", None)
    return method() if callable(method) else datetime.now(UTC)


@private_router.get("/packages")
async def packages(
    request: Request, limit: int = Query(100, ge=1, le=200)
) -> dict[str, object]:
    return {
        "items": request.app.state.radar_repository.list_ui_packages(limit=limit),
        "next_cursor": None,
        "data_as_of": _data_as_of(request).isoformat(),
    }


@private_router.get("/packages/{name:path}")
async def package_detail(name: str, request: Request) -> dict[str, object]:
    try:
        return cast(
            dict[str, object], request.app.state.radar_repository.get_ui_package(name)
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="package not found") from exc


@private_router.get("/evidence/{name:path}")
async def evidence(name: str, request: Request) -> dict[str, object]:
    return {
        "items": request.app.state.radar_repository.list_ui_evidence(name),
        "next_cursor": None,
        "data_as_of": _data_as_of(request).isoformat(),
    }


@private_router.get("/decisions")
async def decisions(
    request: Request, limit: int = Query(100, ge=1, le=200)
) -> dict[str, object]:
    return {
        "items": request.app.state.radar_repository.list_ui_decisions(limit=limit),
        "next_cursor": None,
        "data_as_of": _data_as_of(request).isoformat(),
    }


@private_router.get("/coverage")
async def coverage(request: Request) -> dict[str, object]:
    return cast(dict[str, object], request.app.state.radar_repository.coverage())


@private_router.get("/overview")
async def overview(request: Request) -> dict[str, object]:
    repository = request.app.state.radar_repository
    packages = repository.list_ui_packages(limit=200)
    decisions = repository.list_ui_decisions(limit=20)
    coverage_data = repository.coverage()
    threats = [item for item in packages if item["state"] in {"high_risk", "blocked"}]
    return {
        "data_as_of": _data_as_of(request).isoformat(),
        "guard_status": "operational",
        "active_threats": len(threats),
        "protected_agents": coverage_data["protected_agents"],
        "verified_recommendations": coverage_data["verified_recommendations"],
        "radar_nodes": packages,
        "prioritized_targets": sorted(
            threats, key=lambda item: int(item["attractiveness"]), reverse=True
        )[:20],
        "recent_activity": [
            {
                "id": item["id"],
                "kind": item["result"],
                "label": f"Guard decision: {item['result']}",
                "package_name": item["package_name"],
                "occurred_at": item["occurred_at"],
            }
            for item in decisions
        ],
    }


@private_router.get("/demo")
async def live_demo_status(request: Request) -> dict[str, object]:
    repository = request.app.state.radar_repository
    decisions = repository.list_ui_decisions(limit=1)
    packages = repository.list_ui_packages(limit=1)
    latest = decisions[0] if decisions else None
    package = packages[0] if packages else None
    blocked = latest is not None and latest["result"] == "block"
    detail = repository.get_ui_package(str(package["name"])) if package else None
    return {
        "state": "blocked" if blocked else "ready",
        "completed_steps": ["run-protected"] if blocked else [],
        "available_actions": [],
        "target_package": package["name"] if package else None,
        "unprotected_canary_count": 0,
        "protected_canary_count": 0,
        "package_manager_started": latest["package_manager_started"] if latest else None,
        "message": (
            "SSS Guard blocked the install before the package manager."
            if blocked
            else "Run the protected agent command in the terminal to create live evidence."
        ),
        "scores": {
            "absence_confidence": (detail or {}).get("absence_confidence") or 0,
            "target_attractiveness": (package or {}).get("attractiveness") or 0,
            "package_policy_risk": (package or {}).get("policy_risk") or 0,
        },
        "policy_version": latest["policy"] if latest else "not-yet-evaluated",
        "registration_age_minutes": 0,
    }
