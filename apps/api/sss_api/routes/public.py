"""Read-only, synthetic-only browser view of the local demonstration."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import suppress
from datetime import datetime
from typing import Any, Protocol, cast

from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sss_core import EvidenceScores, PackageIdentity

from sss_api.events import ServerEvent
from sss_api.services.demo import DemoState, DemoStatus

router = APIRouter(prefix="/v1/public", tags=["public-demo"])
aggregate_router = APIRouter(prefix="/v1/public", tags=["public-aggregates"])


@aggregate_router.get("/aggregates")
async def aggregates(request: Request) -> dict[str, Any]:
    repository = request.app.state.radar_repository
    if repository is None:
        return {"data_as_of": datetime.now().astimezone().isoformat(), "groups": []}
    return cast(dict[str, Any], repository.public_aggregates())


class DemoFixture(Protocol):
    package: PackageIdentity
    scores: EvidenceScores
    attack_at: datetime
    first_absence_at: datetime
    registered_at: datetime
    policy_version: str
    registration_age_minutes: int
    protected_agent_attempts: int
    observation_days: int
    verified_model_recommendations: int
    public_failed_references: int
    model_configurations: int


def _fixture(request: Request) -> DemoFixture:
    return cast(DemoFixture, request.app.state.demo_fixture)


def _effective_status(request: Request) -> DemoStatus:
    current = cast(DemoStatus, request.app.state.demo_controller.status())
    if (
        current.state is DemoState.READY
        and request.app.state.install_attempt_store.list_all()
    ):
        return DemoStatus(
            state=DemoState.PROTECTED_BLOCKED,
            canary_count=current.canary_count,
            protected_child_started=False,
            protected_exit_code=23,
        )
    return current


def _package(fixture: DemoFixture, state: DemoState) -> dict[str, Any]:
    package_state = {
        DemoState.READY: "absent",
        DemoState.REPLAYED: "absent",
        DemoState.REGISTERED: "high_risk",
        DemoState.UNPROTECTED: "high_risk",
        DemoState.PROTECTED_BLOCKED: "blocked",
    }[state]
    return {
        "id": "pkg-demo-reserved-synthetic",
        "name": fixture.package.canonical_name,
        "ecosystem": fixture.package.ecosystem.value,
        "state": package_state,
        "attractiveness": fixture.scores.target_attractiveness,
        "policy_risk": fixture.scores.package_policy_risk,
        "last_seen": fixture.attack_at.isoformat(),
    }


def _demo_view(value: DemoStatus, fixture: DemoFixture) -> dict[str, Any]:
    completed = {
        DemoState.READY: [],
        DemoState.REPLAYED: ["replay-evidence"],
        DemoState.REGISTERED: ["replay-evidence", "register-target"],
        DemoState.UNPROTECTED: [
            "replay-evidence",
            "register-target",
            "run-unprotected",
        ],
        DemoState.PROTECTED_BLOCKED: [
            "replay-evidence",
            "register-target",
            "run-unprotected",
            "run-protected",
        ],
    }[value.state]
    view_state = "blocked" if value.state is DemoState.PROTECTED_BLOCKED else (
        "ready" if value.state is DemoState.READY else "running"
    )
    messages = {
        DemoState.READY: "Terminal-first agent demonstration is ready to run.",
        DemoState.REPLAYED: (
            "Synthetic Exasol evidence replayed; register the controlled target next."
        ),
        DemoState.REGISTERED: "Controlled target registered on the same logical npm origin.",
        DemoState.UNPROTECTED: "Unprotected baseline reached the isolated canary once.",
        DemoState.PROTECTED_BLOCKED: (
            "Agent install blocked before pnpm; review it with `sss intervene --watch`."
        ),
    }
    return {
        "state": view_state,
        "completed_steps": completed,
        "available_actions": [],
        "target_package": fixture.package.canonical_name,
        "unprotected_canary_count": value.canary_count,
        "protected_canary_count": 0,
        "package_manager_started": value.protected_child_started,
        "message": messages[value.state],
        "scores": {
            "absence_confidence": fixture.scores.absence_confidence,
            "target_attractiveness": fixture.scores.target_attractiveness,
            "package_policy_risk": fixture.scores.package_policy_risk,
        },
        "policy_version": fixture.policy_version,
        "registration_age_minutes": fixture.registration_age_minutes,
    }


@router.get("/overview")
async def overview(request: Request) -> dict[str, Any]:
    fixture = _fixture(request)
    current = _effective_status(request)
    package = _package(fixture, current.state)
    activity = []
    if current.state is DemoState.PROTECTED_BLOCKED:
        activity.append(
            {
                "id": "activity-protected-block",
                "kind": "blocked",
                "label": "Agent install stopped before pnpm",
                "package_name": fixture.package.canonical_name,
                "occurred_at": fixture.attack_at.isoformat(),
            }
        )
    return {
        "data_as_of": fixture.attack_at.isoformat(),
        "guard_status": "operational",
        "active_threats": 1 if current.state is not DemoState.READY else 0,
        "protected_agents": fixture.protected_agent_attempts,
        "verified_recommendations": fixture.verified_model_recommendations,
        "radar_nodes": [package],
        "prioritized_targets": [package],
        "recent_activity": activity,
    }


@router.get("/packages")
async def packages(request: Request) -> list[dict[str, Any]]:
    return [_package(_fixture(request), _effective_status(request).state)]


@router.get("/packages/{name:path}")
async def package_detail(name: str, request: Request) -> dict[str, Any]:
    fixture = _fixture(request)
    if name != fixture.package.canonical_name:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="package not found")
    package = _package(fixture, _effective_status(request).state)
    return {
        **package,
        "absence_confidence": fixture.scores.absence_confidence,
        "lifecycle": [
            "46 verified recommendations observed",
            "Public registry absence verified",
            "Registration detected on the same origin",
            "Agent installation blocked before pnpm",
        ],
    }


@router.get("/evidence/{name:path}")
async def evidence(name: str, request: Request) -> list[dict[str, Any]]:
    fixture = _fixture(request)
    if name != fixture.package.canonical_name:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="package not found")
    return [
        {
            "id": "evidence-absence",
            "type": "registry",
            "label": "npm absence verified",
            "provenance": "synthetic registry observation",
            "occurred_at": fixture.first_absence_at.isoformat(),
        },
        {
            "id": "evidence-registration",
            "type": "registration",
            "label": "Same-origin registration detected",
            "provenance": "synthetic registry observation",
            "occurred_at": fixture.registered_at.isoformat(),
        },
    ]


@router.get("/decisions")
async def decisions(request: Request) -> list[dict[str, Any]]:
    fixture = _fixture(request)
    return [
        {
            "id": attempt.decision_id,
            "package_name": fixture.package.canonical_name,
            "ecosystem": fixture.package.ecosystem.value,
            "result": attempt.decision.value,
            "policy": fixture.policy_version,
            "occurred_at": attempt.attempted_at.isoformat(),
            "reason_codes": [
                "REGISTERED_AFTER_HALLUCINATION",
                "HIGH_GLOBAL_RECURRENCE",
            ],
            "package_manager_started": attempt.child_started,
            "package_code_executed": False,
        }
        for attempt in request.app.state.install_attempt_store.list_all()
    ]


@router.get("/coverage")
async def coverage(request: Request) -> dict[str, Any]:
    fixture = _fixture(request)
    return {
        "data_as_of": fixture.attack_at.isoformat(),
        "registries": [
            {
                "id": "registry-npm-demo",
                "name": "Controlled npm",
                "state": "operational",
                "detail": "TLS same-origin registry",
            }
        ],
        "services": [
            {
                "id": "service-guard",
                "name": "SSS Guard",
                "state": "operational",
                "detail": "Strict policy loaded from Exasol-backed evidence",
            }
        ],
        "protected_agents": fixture.protected_agent_attempts,
        "observation_days": fixture.observation_days,
        "verified_recommendations": fixture.verified_model_recommendations,
        "public_failed_references": fixture.public_failed_references,
        "model_configurations": fixture.model_configurations,
    }


@router.get("/demo")
async def demo(request: Request) -> dict[str, Any]:
    return _demo_view(_effective_status(request), _fixture(request))


@router.get("/events")
async def events(
    request: Request,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
) -> StreamingResponse:
    try:
        start_id = max(int(last_event_id or "0"), 0)
    except ValueError:
        start_id = 0
    return StreamingResponse(
        _public_event_stream(request, start_id=start_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _public_event_stream(request: Request, *, start_id: int) -> AsyncIterator[str]:
    broker = request.app.state.event_broker
    stream = broker.stream(after_id=start_id).__aiter__()
    pending: asyncio.Task[ServerEvent] | None = None
    try:
        while True:
            if await request.is_disconnected():
                return
            if pending is None:
                pending = asyncio.create_task(stream.__anext__())
            completed, _ = await asyncio.wait(
                {pending}, timeout=request.app.state.settings.sse_heartbeat_seconds
            )
            if not completed:
                yield ": heartbeat\n\n"
                continue
            event = pending.result()
            pending = None
            payload = json.dumps({"occurred_at": event.occurred_at.isoformat()})
            yield f"id: {event.event_id}\nevent: {event.event_type}\ndata: {payload}\n\n"
    finally:
        if pending is not None and not pending.done():
            pending.cancel()
            with suppress(asyncio.CancelledError):
                await pending
