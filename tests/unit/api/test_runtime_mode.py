from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest
import sss_api.main
import sss_core
from sss_api.config import ApiSettings, ConfigurationError
from sss_api.events import EventBroker
from sss_api.main import create_app
from sss_api.services.attempts import AttemptStore
from sss_api.services.guard import GuardService
from sss_api.services.interventions import InterventionStore
from sss_core import POLICY_VERSION, PackageIdentity, PolicyContext, PolicyEngine


class UnknownEvidenceProvider:
    def context_for(self, package: PackageIdentity) -> PolicyContext:
        raise AssertionError(f"Guard must not be called while composing the app: {package!r}")


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
    credentials_file.write_text('{"credentials": []}', encoding="utf-8")
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
    monkeypatch.setattr(sss_api.main, "load_demo_fixture", load_fixture, raising=False)

    app = create_app(
        settings=_production_settings(tmp_path),
        service_factory=_fake_production_services,
    )

    assert app.state.runtime_mode is sss_core.RuntimeMode.PRODUCTION
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


def test_production_composition_fails_clearly_until_exasol_provider_is_wired(
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

    with pytest.raises(ConfigurationError, match=r"incomplete.*ExasolEvidenceProvider"):
        sss_api.main.build_production_services(settings)
