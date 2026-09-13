"""FastAPI composition for the independently owned API boundary."""

from __future__ import annotations

from os import environ
from pathlib import Path
from typing import cast

from fastapi import FastAPI
from sss_core import PolicyEngine
from sss_core.config import ExasolSettings
from sss_core.repositories.exasol import (
    ExasolConnection,
    ExasolPolicyRepository,
    SchemaReadinessChecker,
)

from sss_api.config import ApiSettings
from sss_api.events import EventBroker
from sss_api.middleware.body_limit import RequestBodyLimitMiddleware
from sss_api.middleware.request_id import RequestIdMiddleware
from sss_api.routes import (
    approvals,
    attempts,
    demo,
    events,
    guard,
    health,
    interventions,
    observations,
    public,
)
from sss_api.services.approvals import ApprovalService
from sss_api.services.attempts import AttemptSink, AttemptStore
from sss_api.services.control_room import ExasolControlRoomService, RuntimeControlRoomService
from sss_api.services.demo import DemoController, NoopDemoRepository
from sss_api.services.guard import (
    DecisionSink,
    EvidenceProvider,
    ExasolEvidenceProvider,
    FailClosedEvidenceProvider,
    GuardService,
)
from sss_api.services.interventions import InterventionStore
from sss_api.services.observations import ExasolObservationSink, ObservationSink, ObservationStore
from sss_api.services.persistence import ExasolAttemptSink, ExasolDecisionSink
from sss_api.services.readiness import ReadinessService

ROOT = Path(environ.get("SSS_RUNTIME_ROOT", Path.cwd())).resolve()


def create_app(
    *,
    settings: ApiSettings | None = None,
    event_broker: EventBroker | None = None,
    guard_service: GuardService | None = None,
    intervention_store: InterventionStore | None = None,
    install_attempt_store: AttemptStore | None = None,
    approval_service: ApprovalService | None = None,
    demo_controller: DemoController | None = None,
    observation_store: ObservationStore | None = None,
) -> FastAPI:
    resolved_settings = settings or ApiSettings.from_env()
    app = FastAPI(title="SSS API", version="0.1.0")
    app.state.settings = resolved_settings
    broker = event_broker or EventBroker(capacity=resolved_settings.sse_buffer_size)
    store = intervention_store or InterventionStore()
    exasol_connection: ExasolConnection | None = None
    exasol_ready = False
    observation_sink: ObservationSink | None = None
    attempt_sink: AttemptSink | None = None
    decision_sink: DecisionSink | None = None
    schema_checker = SchemaReadinessChecker(ROOT / "infra/exasol/migrations")
    if approval_service is None and resolved_settings.approval_signing_key is not None:
        approval_service = ApprovalService(
            signing_key=resolved_settings.approval_signing_key.encode()
        )
    if guard_service is None:
        evidence_provider: EvidenceProvider = FailClosedEvidenceProvider()
        if resolved_settings.exasol_required:
            try:
                import pyexasol  # type: ignore[import-untyped]

                exasol_settings = ExasolSettings.from_env()
                connection = cast(
                    ExasolConnection,
                    pyexasol.connect(
                        dsn=exasol_settings.dsn,
                        user=exasol_settings.user,
                        password=exasol_settings.password,
                        schema=exasol_settings.schema,
                        autocommit=False,
                    ),
                )
                exasol_connection = connection
                readiness = schema_checker.check(connection)
                if readiness.ready:
                    exasol_ready = True
                    observation_sink = ExasolObservationSink(connection)
                    attempt_sink = ExasolAttemptSink(connection)
                    decision_sink = ExasolDecisionSink(connection)
                    evidence_provider = ExasolEvidenceProvider(ExasolPolicyRepository(connection))
            except Exception:
                exasol_connection = None
        guard_service = GuardService(
            PolicyEngine(),
            evidence_provider,
            store,
            broker,
            decision_sink,
            approval_service,
        )
    attempts_store = install_attempt_store or AttemptStore(attempt_sink)
    observations_store = observation_store or ObservationStore(observation_sink)
    app.state.event_broker = broker
    app.state.guard_service = guard_service
    app.state.intervention_store = store
    app.state.install_attempt_store = attempts_store
    app.state.approval_service = approval_service
    app.state.observation_store = observations_store
    app.state.control_room_service = (
        ExasolControlRoomService(exasol_connection)
        if exasol_connection is not None and exasol_ready
        else RuntimeControlRoomService(observations_store, guard_service, attempts_store)
    )
    app.state.readiness_service = ReadinessService(
        settings=resolved_settings,
        connection=exasol_connection,
        schema_checker=schema_checker,
    )
    app.state.demo_controller = demo_controller or DemoController(repository=NoopDemoRepository())
    app.add_middleware(RequestBodyLimitMiddleware, max_bytes=resolved_settings.max_body_bytes)
    app.add_middleware(RequestIdMiddleware)
    app.include_router(health.router)
    app.include_router(public.router)
    app.include_router(events.router)
    app.include_router(guard.router)
    app.include_router(interventions.router)
    app.include_router(attempts.router)
    app.include_router(observations.router)
    app.include_router(approvals.router)
    app.include_router(demo.router)
    return app


app = create_app()
