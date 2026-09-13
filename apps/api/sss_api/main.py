"""FastAPI composition for explicit production, demo, and test runtimes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import FastAPI
from sss_core import RuntimeMode
from sss_core.config import ExasolSettings

from sss_api.config import ApiSettings, ConfigurationError
from sss_api.events import EventBroker
from sss_api.middleware.body_limit import RequestBodyLimitMiddleware
from sss_api.middleware.request_id import RequestIdMiddleware
from sss_api.routes import approvals, attempts, events, guard, health, interventions
from sss_api.services.approvals import ApprovalService
from sss_api.services.attempts import AttemptStore
from sss_api.services.guard import GuardService
from sss_api.services.interventions import InterventionStore


@dataclass(frozen=True, slots=True)
class ServiceContainer:
    event_broker: EventBroker
    guard_service: GuardService
    intervention_store: InterventionStore
    install_attempt_store: AttemptStore
    approval_service: ApprovalService | None
    demo_controller: object | None = None
    demo_fixture: object | None = None


ServiceFactory = Callable[[ApiSettings], ServiceContainer]


def build_production_services(settings: ApiSettings) -> ServiceContainer:
    if settings.runtime_mode is not RuntimeMode.PRODUCTION:
        raise ConfigurationError("production services require production runtime mode")
    try:
        ExasolSettings.from_env()
    except ValueError as exc:
        raise ConfigurationError(
            f"production requires complete Exasol connection configuration: {exc}"
        ) from exc
    raise ConfigurationError(
        "production service composition is incomplete: "
        "ExasolEvidenceProvider will be wired by Task 5"
    )


def build_services(settings: ApiSettings) -> ServiceContainer:
    if settings.runtime_mode is RuntimeMode.PRODUCTION:
        return build_production_services(settings)

    from sss_api.demo_composition import build_demo_services

    return build_demo_services(settings)


def create_app(
    *,
    settings: ApiSettings | None = None,
    service_factory: ServiceFactory | None = None,
    install_attempt_store: AttemptStore | None = None,
    approval_service: ApprovalService | None = None,
    demo_controller: object | None = None,
) -> FastAPI:
    resolved_settings = settings or ApiSettings.from_env()
    services = (service_factory or build_services)(resolved_settings)
    if resolved_settings.runtime_mode is RuntimeMode.PRODUCTION and (
        services.demo_fixture is not None
        or services.demo_controller is not None
        or demo_controller is not None
    ):
        raise ConfigurationError("production service composition cannot include demo state")
    app = FastAPI(title="SSS API", version="0.1.0")
    app.state.settings = resolved_settings
    app.state.runtime_mode = resolved_settings.runtime_mode
    app.state.event_broker = services.event_broker
    app.state.guard_service = services.guard_service
    app.state.intervention_store = services.intervention_store
    app.state.install_attempt_store = install_attempt_store or services.install_attempt_store
    app.state.approval_service = approval_service or services.approval_service

    resolved_demo_controller = demo_controller or services.demo_controller
    if services.demo_fixture is not None and resolved_demo_controller is not None:
        app.state.demo_fixture = services.demo_fixture
        app.state.demo_controller = resolved_demo_controller

    app.add_middleware(RequestBodyLimitMiddleware, max_bytes=resolved_settings.max_body_bytes)
    app.add_middleware(RequestIdMiddleware)
    app.include_router(health.router)
    app.include_router(events.router)
    app.include_router(guard.router)
    app.include_router(interventions.router)
    app.include_router(attempts.router)
    app.include_router(approvals.router)
    if services.demo_fixture is not None:
        from sss_api.routes import demo, public

        app.include_router(public.router)
        app.include_router(demo.router)
    return app
