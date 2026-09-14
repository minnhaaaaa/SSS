"""Synthetic-only service composition for explicit demo and test runtimes."""

from __future__ import annotations

from os import environ
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from sss_core import (
    CandidateStatus,
    EvidenceScores,
    PackageIdentity,
    PolicyContext,
    PolicyEngine,
    RuntimeMode,
)
from sss_core.config import ExasolSettings
from sss_core.demo import FixedDemoFixture, load_demo_fixture
from sss_core.registries.base import RegistryOutcome
from sss_core.repositories.exasol import ExasolPolicyRepository, SchemaReadinessChecker

from sss_api.config import ApiSettings, ConfigurationError
from sss_api.events import EventBroker
from sss_api.services.approvals import ApprovalService
from sss_api.services.attempts import AttemptStore
from sss_api.services.demo import DemoController, NoopDemoRepository
from sss_api.services.guard import EvidenceProvider, GuardService
from sss_api.services.interventions import InterventionStore

if TYPE_CHECKING:
    from sss_api.main import ServiceContainer


class RadarRepository(Protocol):
    def load_evidence(self, *, ecosystem: str, origin: str, name: str) -> dict[str, object]: ...


class FixedDemoEvidenceProvider:
    def __init__(self, fixture: FixedDemoFixture) -> None:
        self._fixture = fixture

    def context_for(self, package: PackageIdentity) -> PolicyContext:
        if package == self._fixture.package:
            return PolicyContext(
                candidate_status=CandidateStatus.REGISTERED_AFTER_ABSENCE,
                registry_outcome=RegistryOutcome.REGISTERED,
                scores=self._fixture.scores,
                approved_source=True,
                strict_mode=True,
                interactive=False,
                historical_hallucination=True,
            )
        return PolicyContext(
            candidate_status=CandidateStatus.AMBIGUOUS,
            registry_outcome=RegistryOutcome.UNKNOWN_NETWORK,
            scores=EvidenceScores(None, 0, 0),
            approved_source=False,
            strict_mode=True,
            interactive=False,
            historical_hallucination=False,
        )


class ExasolDemoEvidenceProvider:
    """Require Exasol's private Radar row before returning the frozen demo assessment."""

    def __init__(self, fixture: FixedDemoFixture, repository: RadarRepository) -> None:
        self._fixture = fixture
        self._repository = repository
        self._fallback = FixedDemoEvidenceProvider(fixture)

    def context_for(self, package: PackageIdentity) -> PolicyContext:
        if package != self._fixture.package:
            return self._fallback.context_for(package)
        row = self._repository.load_evidence(
            ecosystem=package.ecosystem.value,
            origin=package.registry_origin,
            name=package.canonical_name,
        )
        expected = {
            "ECOSYSTEM": "npm",
            "REGISTRY_ORIGIN": "https://npm.demo.sss.test",
            "CANONICAL_NAME": "@sss-demo/reserved-synthetic",
            "STATUS": "registered_after_absence",
            "VERIFIED_MODEL_RECOMMENDATIONS": 46,
            "MODEL_CONFIGURATIONS": 3,
            "PROTECTED_AGENT_ATTEMPTS": 8,
            "PUBLIC_FAILED_REFERENCES": 5,
            "OBSERVATION_DAYS": 11,
        }
        if any(row.get(key) != value for key, value in expected.items()):
            return PolicyContext(
                candidate_status=CandidateStatus.AMBIGUOUS,
                registry_outcome=RegistryOutcome.UNKNOWN_RESPONSE,
                scores=EvidenceScores(None, 0, 0),
                approved_source=False,
                strict_mode=True,
                interactive=False,
                historical_hallucination=False,
            )
        return self._fallback.context_for(package)


def build_demo_services(settings: ApiSettings) -> ServiceContainer:
    if settings.runtime_mode not in {RuntimeMode.DEMO, RuntimeMode.TEST}:
        raise ConfigurationError("demo services require demo or test runtime mode")

    # Imported here to keep production module loading disjoint from fixture composition.
    from sss_api.main import ServiceContainer

    root = Path(environ.get("SSS_RUNTIME_ROOT", Path.cwd())).resolve()
    fixture = load_demo_fixture(root / "demo/fixtures/fixed-intelligence.json")
    broker = EventBroker(capacity=settings.sse_buffer_size)
    interventions = InterventionStore()
    evidence_provider: EvidenceProvider = FixedDemoEvidenceProvider(fixture)
    if settings.exasol_required:
        import pyexasol  # type: ignore[import-untyped]

        exasol_settings = ExasolSettings.from_env()
        connection = pyexasol.connect(
            dsn=exasol_settings.dsn,
            user=exasol_settings.user,
            password=exasol_settings.password,
            schema=exasol_settings.schema,
            autocommit=False,
        )
        readiness = SchemaReadinessChecker(root / "infra/exasol/migrations").check(connection)
        if not readiness.ready:
            raise RuntimeError("Exasol schema is not ready for demo Guard decisions")
        evidence_provider = ExasolDemoEvidenceProvider(
            fixture,
            ExasolPolicyRepository(connection),
        )

    approval_service = None
    if settings.approval_signing_key is not None:
        approval_service = ApprovalService(signing_key=settings.approval_signing_key.encode())
    return ServiceContainer(
        event_broker=broker,
        guard_service=GuardService(
            PolicyEngine(),
            evidence_provider,
            interventions,
            broker,
        ),
        intervention_store=interventions,
        install_attempt_store=AttemptStore(),
        approval_service=approval_service,
        demo_controller=DemoController(repository=NoopDemoRepository()),
        demo_fixture=fixture,
    )
