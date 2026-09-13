"""FastAPI composition for the independently owned API boundary."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from sss_core import PolicyEngine
from sss_core.demo import load_demo_fixture

from sss_api.config import ApiSettings
from sss_api.events import EventBroker
from sss_api.middleware.body_limit import RequestBodyLimitMiddleware
from sss_api.middleware.request_id import RequestIdMiddleware
from sss_api.routes import approvals, attempts, demo, events, guard, health, interventions
from sss_api.services.approvals import ApprovalService
from sss_api.services.attempts import AttemptStore
from sss_api.services.demo import DemoController, NoopDemoRepository
from sss_api.services.guard import FixedDemoEvidenceProvider, GuardService
from sss_api.services.interventions import InterventionStore


def create_app(
    *,
    settings: ApiSettings | None = None,
    event_broker: EventBroker | None = None,
    guard_service: GuardService | None = None,
    intervention_store: InterventionStore | None = None,
    install_attempt_store: AttemptStore | None = None,
    approval_service: ApprovalService | None = None,
    demo_controller: DemoController | None = None,
) -> FastAPI:
    resolved_settings = settings or ApiSettings.from_env()
    app = FastAPI(title="SSS API", version="0.1.0")
    app.state.settings = resolved_settings
    broker = event_broker or EventBroker(capacity=resolved_settings.sse_buffer_size)
    store = intervention_store or InterventionStore()
    attempts_store = install_attempt_store or AttemptStore()
    if approval_service is None and resolved_settings.approval_signing_key is not None:
        approval_service = ApprovalService(
            signing_key=resolved_settings.approval_signing_key.encode()
        )
    if guard_service is None:
        fixture_path = Path(__file__).resolve().parents[3] / "demo/fixtures/fixed-intelligence.json"
        guard_service = GuardService(
            PolicyEngine(),
            FixedDemoEvidenceProvider(load_demo_fixture(fixture_path)),
            store,
            broker,
        )
    app.state.event_broker = broker
    app.state.guard_service = guard_service
    app.state.intervention_store = store
    app.state.install_attempt_store = attempts_store
    app.state.approval_service = approval_service
    app.state.demo_controller = demo_controller or DemoController(repository=NoopDemoRepository())
    app.add_middleware(RequestBodyLimitMiddleware, max_bytes=resolved_settings.max_body_bytes)
    app.add_middleware(RequestIdMiddleware)
    app.include_router(health.router)
    app.include_router(events.router)
    app.include_router(guard.router)
    app.include_router(interventions.router)
    app.include_router(attempts.router)
    app.include_router(approvals.router)
    app.include_router(demo.router)
    return app


app = create_app()
