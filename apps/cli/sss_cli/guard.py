"""Pre-execution package-manager Guard."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Protocol

from sss_core import Decision, InstallRequest

from sss_cli.adapters import GuardAdapterError, GuardDecisionResult
from sss_cli.install_intent import parse_install_argv
from sss_cli.process import ProcessConfigurationError, ProcessResult

BLOCK_EXIT_CODE = 23
ASSESSMENT_UNAVAILABLE_EXIT_CODE = 24


class GuardClient(Protocol):
    def check(self, request: InstallRequest) -> GuardDecisionResult: ...

    def record_attempt(self, **payload: object) -> None: ...


class ManagerRunner(Protocol):
    def run(
        self,
        manager: str,
        arguments: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str],
    ) -> ProcessResult: ...


class GuardRunner:
    def __init__(
        self,
        *,
        client: GuardClient,
        process_runner: ManagerRunner,
        registry_origin: str,
        project_id: str,
        agent_family: str,
        artifact_sha256: str | None,
        cwd: Path,
        environment: Mapping[str, str],
        write: Callable[[str], None],
        pypi_registry_origin: str = "https://pypi.org",
    ) -> None:
        self._client = client
        self._process_runner = process_runner
        self._registry_origin = registry_origin
        self._project_id = project_id
        self._agent_family = agent_family
        self._artifact_sha256 = artifact_sha256
        self._cwd = cwd
        self._environment = environment
        self._write = write
        self._pypi_registry_origin = pypi_registry_origin

    def run(self, manager: str, arguments: Sequence[str]) -> int:
        argv = tuple(arguments)
        try:
            requests, assessments = self._assess(manager, argv)
        except ValueError as exc:
            self._write(f"SSS BLOCK — {exc}")
            self._write("Installation was not started.")
            return BLOCK_EXIT_CODE
        except GuardAdapterError as exc:
            self._write(f"SSS UNAVAILABLE — {exc}")
            self._write("Installation was not started.")
            return ASSESSMENT_UNAVAILABLE_EXIT_CODE

        blocked = next(
            (
                (request, assessment)
                for request, assessment in zip(requests, assessments, strict=True)
                if assessment.decision is not Decision.ALLOW or not assessment.child_process_allowed
            ),
            None,
        )
        if blocked is not None:
            blocked_request, blocked_assessment = blocked
            self._render_block(blocked_request, blocked_assessment)
            for assessment in assessments:
                self._record_attempt(manager, argv, assessment, child_started=False)
            return BLOCK_EXIT_CODE

        try:
            result = self._process_runner.run(
                manager,
                argv,
                cwd=self._cwd,
                env=self._environment,
            )
        except ProcessConfigurationError as exc:
            self._write(f"SSS UNAVAILABLE — {exc}")
            for assessment in assessments:
                self._record_attempt(manager, argv, assessment, child_started=False)
            return ASSESSMENT_UNAVAILABLE_EXIT_CODE
        for assessment in assessments:
            self._record_attempt(manager, argv, assessment, child_started=result.child_started)
        return result.returncode

    def check_only(self, manager: str, arguments: Sequence[str]) -> int:
        """Assess an install vector without ever starting its package manager."""

        argv = tuple(arguments)
        try:
            requests, assessments = self._assess(manager, argv)
        except ValueError as exc:
            self._write(f"SSS BLOCK — {exc}")
            return BLOCK_EXIT_CODE
        except GuardAdapterError as exc:
            self._write(f"SSS UNAVAILABLE — {exc}")
            return ASSESSMENT_UNAVAILABLE_EXIT_CODE
        for request, assessment in zip(requests, assessments, strict=True):
            self._render_assessment(request, assessment)
        return (
            0
            if all(
                item.decision is Decision.ALLOW and item.child_process_allowed
                for item in assessments
            )
            else BLOCK_EXIT_CODE
        )

    def _assess(
        self, manager: str, arguments: tuple[str, ...]
    ) -> tuple[tuple[InstallRequest, ...], tuple[GuardDecisionResult, ...]]:
        requests = parse_install_argv(
            manager,
            arguments,
            registry_origin=self._registry_origin,
            pypi_registry_origin=self._pypi_registry_origin,
            project_id=self._project_id,
            agent_family=self._agent_family,
            artifact_sha256=self._artifact_sha256,
        )
        return requests, tuple(self._client.check(request) for request in requests)

    def _render_block(
        self,
        request: InstallRequest,
        assessment: GuardDecisionResult,
    ) -> None:
        self._write(f"SSS BLOCK — {request.package.canonical_name}@{request.version_spec}")
        self._write(f"Registry: {request.package.registry_origin}")
        self._write(f"Absence confidence: {assessment.scores.absence_confidence}")
        self._write(f"Target attractiveness: {assessment.scores.target_attractiveness}")
        self._write(f"Package policy risk: {assessment.scores.package_policy_risk}")
        self._write(f"Reasons: {', '.join(assessment.reason_codes)}")
        if assessment.intervention_id is not None:
            self._write(f"Intervention: {assessment.intervention_id}")
        self._write("Installation was not started.")

    def _render_assessment(
        self,
        request: InstallRequest,
        assessment: GuardDecisionResult,
    ) -> None:
        self._write(
            f"{assessment.decision.value.upper()} "
            f"{request.package.canonical_name}@{request.version_spec}"
        )
        self._write(f"Policy: {assessment.policy_version}")
        self._write(f"Reasons: {', '.join(assessment.reason_codes)}")

    def _record_attempt(
        self,
        manager: str,
        arguments: tuple[str, ...],
        assessment: GuardDecisionResult,
        *,
        child_started: bool,
    ) -> None:
        self._client.record_attempt(
            decision_id=assessment.decision_id,
            manager=manager,
            arguments=arguments,
            agent_family=self._agent_family,
            project_id=self._project_id,
            decision=assessment.decision.value,
            child_started=child_started,
        )
