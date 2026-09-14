from __future__ import annotations

import sys
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any, cast
from unittest.mock import Mock

import pytest
import sss_api.main
import sss_core
import sss_core.demo
from sss_api.config import ApiSettings, ConfigurationError
from sss_api.events import EventBroker
from sss_api.main import create_app
from sss_api.services.attempts import AttemptStore
from sss_api.services.guard import GuardService
from sss_api.services.interventions import InterventionStore
from sss_core import (
    POLICY_VERSION,
    CandidateStatus,
    Ecosystem,
    EvidenceScores,
    InstallRequest,
    PackageIdentity,
    PolicyContext,
    PolicyEngine,
)
from sss_core.registries.base import RegistryOutcome


class UnknownEvidenceProvider:
    def context_for(self, package: PackageIdentity) -> PolicyContext:
        raise AssertionError(f"Guard must not be called while composing the app: {package!r}")


class BlockingEvidenceProvider:
    def context_for(self, package: PackageIdentity) -> PolicyContext:
        return PolicyContext(
            candidate_status=CandidateStatus.REGISTERED_AFTER_ABSENCE,
            registry_outcome=RegistryOutcome.REGISTERED,
            scores=EvidenceScores(100, 95, 75),
            approved_source=True,
            strict_mode=True,
            interactive=False,
            historical_hallucination=True,
        )


def _production_values(credentials_file: Path) -> dict[str, str]:
    return {
        "SSS_ENV": "production",
        "SSS_EXASOL_REQUIRED": "true",
        "SSS_APPROVAL_SIGNING_KEY": "production-signing-key-with-at-least-32-bytes",
        "SSS_CREDENTIALS_FILE": str(credentials_file),
        "SSS_POLICY_VERSION": POLICY_VERSION,
    }


def _production_settings(tmp_path: Path) -> ApiSettings:
    credentials_file = tmp_path / "credentials.json"
    credentials_file.write_text(
        '{"credentials":[{"credential_id":"test-agent","token_sha256":"'
        + "a" * 64
        + '\",\"scopes\":[\"agent:check\"],\"enabled\":true}]}',
        encoding="utf-8",
    )
    credentials_file.chmod(0o600)
    return ApiSettings.from_env(_production_values(credentials_file))


def _fake_production_services(settings: ApiSettings) -> sss_api.main.ServiceContainer:
    assert settings.runtime_mode is sss_core.RuntimeMode.PRODUCTION
    broker = EventBroker(capacity=settings.sse_buffer_size)
    interventions = InterventionStore()
    return sss_api.main.ServiceContainer(
        event_broker=broker,
        guard_service=GuardService(
            PolicyEngine(),
            UnknownEvidenceProvider(),
            interventions,
            broker,
        ),
        intervention_store=interventions,
        install_attempt_store=AttemptStore(),
        approval_service=None,
    )


def _blocking_production_services(settings: ApiSettings) -> sss_api.main.ServiceContainer:
    services = _fake_production_services(settings)
    return replace(
        services,
        guard_service=GuardService(
            PolicyEngine(),
            BlockingEvidenceProvider(),
            services.intervention_store,
            services.event_broker,
        ),
    )


def _install_request() -> InstallRequest:
    return InstallRequest(
        request_id="req-runtime-coherence",
        project_id="project-runtime",
        agent_family="codex",
        package=PackageIdentity(
            ecosystem=Ecosystem.NPM,
            registry_origin="https://registry.npmjs.org",
            canonical_name="runtime-coherence-package",
        ),
        version_spec="1.0.0",
        direct_url=None,
        artifact_sha256="b" * 64,
        is_direct=True,
    )


def test_runtime_mode_is_derived_from_the_explicit_environment() -> None:
    settings = ApiSettings.from_env({"SSS_ENV": "test"})

    assert settings.runtime_mode is sss_core.RuntimeMode.TEST


def test_unsupported_runtime_mode_is_rejected_instead_of_selecting_demo() -> None:
    with pytest.raises(ConfigurationError, match="runtime mode"):
        ApiSettings.from_env({"SSS_ENV": "development"})


def test_missing_runtime_mode_does_not_select_demo() -> None:
    with pytest.raises(ConfigurationError, match="production"):
        ApiSettings.from_env({})


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"SSS_EXASOL_REQUIRED": "false"}, "Exasol"),
        ({"SSS_APPROVAL_SIGNING_KEY": ""}, "signing key"),
        (
            {"SSS_APPROVAL_SIGNING_KEY": "demo-only-signing-key-not-for-production"},
            "non-demo signing key",
        ),
        ({"SSS_CREDENTIALS_FILE": ""}, "credentials file"),
        ({"SSS_CREDENTIALS_FILE": "/does/not/exist.json"}, "credentials file"),
        ({"SSS_POLICY_VERSION": "unexpected-policy"}, "policy version"),
    ],
)
def test_production_rejects_missing_or_demo_prerequisites(
    tmp_path: Path,
    overrides: Mapping[str, str],
    message: str,
) -> None:
    credentials_file = tmp_path / "credentials.json"
    credentials_file.write_text('{"credentials": []}', encoding="utf-8")
    values = {**_production_values(credentials_file), **overrides}

    with pytest.raises(ConfigurationError, match=message):
        ApiSettings.from_env(values)


def test_production_app_does_not_load_or_expose_demo_fixture(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    load_fixture = Mock(side_effect=AssertionError("production loaded the demo fixture"))
    monkeypatch.setattr(sss_core.demo, "load_demo_fixture", load_fixture)
    monkeypatch.delitem(sys.modules, "sss_api.demo_composition", raising=False)

    app = create_app(
        settings=_production_settings(tmp_path),
        service_factory=_fake_production_services,
    )

    assert app.state.runtime_mode is sss_core.RuntimeMode.PRODUCTION
    assert "sss_api.demo_composition" not in sys.modules
    assert not hasattr(app.state, "demo_fixture")
    route_paths = {route.path for route in app.routes if hasattr(route, "path")}
    assert "/v1/demo/status" not in route_paths
    assert "/v1/public/demo" not in route_paths
    load_fixture.assert_not_called()


def test_production_rejects_a_factory_that_injects_demo_state(tmp_path: Path) -> None:
    def unsafe_factory(settings: ApiSettings) -> sss_api.main.ServiceContainer:
        return replace(
            _fake_production_services(settings),
            demo_controller=object(),
            demo_fixture=object(),
        )

    with pytest.raises(ConfigurationError, match=r"production.*demo"):
        create_app(settings=_production_settings(tmp_path), service_factory=unsafe_factory)


def test_create_app_rejects_an_individual_coupled_service_override(tmp_path: Path) -> None:
    untyped_create_app = cast(Any, create_app)
    with pytest.raises(TypeError, match="event_broker"):
        untyped_create_app(
            settings=_production_settings(tmp_path),
            service_factory=_fake_production_services,
            event_broker=EventBroker(capacity=8),
        )


async def test_service_container_keeps_guard_events_and_interventions_coherent(
    tmp_path: Path,
) -> None:
    settings = _production_settings(tmp_path)
    services = _blocking_production_services(settings)
    app = create_app(settings=settings, service_factory=lambda _settings: services)

    assessment = await app.state.guard_service.check(_install_request())

    assert assessment.intervention_id is not None
    assert app.state.event_broker is services.event_broker
    assert app.state.intervention_store is services.intervention_store
    delivered_events = app.state.event_broker.snapshot()
    visible_interventions = app.state.intervention_store.list_pending()
    assert len(delivered_events) == 1
    assert delivered_events[0].payload["intervention_id"] == assessment.intervention_id
    assert len(visible_interventions) == 1
    assert visible_interventions[0].intervention_id == assessment.intervention_id


def test_production_composition_wires_exasol_provider_and_durable_services(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    settings = _production_settings(tmp_path)
    for key, value in {
        "SSS_EXASOL_DSN": "exasol.internal:8563",
        "SSS_EXASOL_USER": "sss_service",
        "SSS_EXASOL_PASSWORD": "not-a-real-secret",
        "SSS_EXASOL_SCHEMA": "SSS",
    }.items():
        monkeypatch.setenv(key, value)

    import pyexasol

    connection = Mock()
    monkeypatch.setattr(pyexasol, "connect", Mock(return_value=connection))
    monkeypatch.setattr(
        sss_api.main.SchemaReadinessChecker,
        "check",
        Mock(return_value=Mock(ready=True)),
    )

    services = sss_api.main.build_production_services(settings)

    assert services.exasol_connection is connection
    assert services.observation_repository is not None
    assert services.radar_repository is not None
    assert services.operational_repository is not None
    assert services.credential_audit_sink is not None
