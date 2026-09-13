"""Pre-execution package-manager Guard."""

from __future__ import annotations

import hashlib
import re
import shlex
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Protocol

from sss_core import Decision, Ecosystem, InstallRequest
from sss_core.extraction import PackageSource, UnsafeInputError
from sss_core.extraction.npm import extract_npm_mentions
from sss_core.identity import canonicalize_identity

from sss_cli.adapters import GuardAdapterError, GuardDecisionResult
from sss_cli.process import ProcessResult

BLOCK_EXIT_CODE = 23
_EXACT_NPM_VERSION = re.compile(
    r"^(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?$"
)
_SHELL_TOKENS = frozenset({";", "&&", "||", "|", ">", ">>", "<", "<<"})


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


def parse_install_argv(
    manager: str,
    arguments: Sequence[str],
    *,
    registry_origin: str,
    project_id: str,
    agent_family: str,
    artifact_sha256: str,
) -> tuple[InstallRequest, ...]:
    normalized_manager = manager.casefold()
    argv = tuple(arguments)
    if normalized_manager != "pnpm" or not argv or argv[0] != "add":
        raise ValueError("strict demo mode supports only pnpm add")
    if len(artifact_sha256) != 64 or any(c not in "0123456789abcdef" for c in artifact_sha256):
        raise ValueError("strict demo mode requires a lowercase SHA-256")
    if any(_unsafe_argument(argument) for argument in argv):
        raise ValueError("package-manager arguments contain unsafe shell syntax")
    try:
        mentions = extract_npm_mentions(shlex.join((normalized_manager, *argv)))
    except UnsafeInputError as exc:
        raise ValueError("package-manager arguments contain unsafe shell syntax") from exc
    if not mentions:
        raise ValueError("pnpm add must include at least one package")
    requests: list[InstallRequest] = []
    for mention in mentions:
        if mention.source is not PackageSource.REGISTRY or mention.requested_registry is not None:
            raise ValueError("strict demo mode allows only the configured npm registry")
        if mention.version_spec is None or not _EXACT_NPM_VERSION.fullmatch(mention.version_spec):
            raise ValueError("strict demo mode requires an exact npm version")
        package = canonicalize_identity(
            Ecosystem.NPM,
            registry_origin,
            mention.canonical_name,
        )
        request_key = "\0".join(
            (
                project_id,
                agent_family,
                normalized_manager,
                *argv,
                package.registry_origin,
                package.canonical_name,
                mention.version_spec,
                artifact_sha256,
            )
        )
        requests.append(
            InstallRequest(
                request_id=hashlib.sha256(request_key.encode()).hexdigest(),
                project_id=project_id,
                agent_family=agent_family,
                package=package,
                version_spec=mention.version_spec,
                direct_url=None,
                artifact_sha256=artifact_sha256,
                is_direct=True,
            )
        )
    return tuple(requests)


def _unsafe_argument(argument: str) -> bool:
    return (
        not argument
        or argument in _SHELL_TOKENS
        or "\x00" in argument
        or "\r" in argument
        or "\n" in argument
        or "$(" in argument
        or "`" in argument
    )


class GuardRunner:
    def __init__(
        self,
        *,
        client: GuardClient,
        process_runner: ManagerRunner,
        registry_origin: str,
        project_id: str,
        agent_family: str,
        artifact_sha256: str,
        cwd: Path,
        environment: Mapping[str, str],
        write: Callable[[str], None],
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

    def run(self, manager: str, arguments: Sequence[str]) -> int:
        argv = tuple(arguments)
        try:
            requests = parse_install_argv(
                manager,
                argv,
                registry_origin=self._registry_origin,
                project_id=self._project_id,
                agent_family=self._agent_family,
                artifact_sha256=self._artifact_sha256,
            )
            assessments = tuple(self._client.check(request) for request in requests)
        except (GuardAdapterError, ValueError) as exc:
            self._write(f"SSS BLOCK — {exc}")
            self._write("Installation was not started.")
            return BLOCK_EXIT_CODE

        blocked = next(
            (
                assessment
                for assessment in assessments
                if assessment.decision is not Decision.ALLOW
                or not assessment.child_process_allowed
            ),
            None,
        )
        if blocked is not None:
            self._render_block(requests[0], blocked)
            self._record_attempt(manager, argv, blocked, child_started=False)
            return BLOCK_EXIT_CODE

        result = self._process_runner.run(
            manager,
            argv,
            cwd=self._cwd,
            env=self._environment,
        )
        self._record_attempt(manager, argv, assessments[0], child_started=result.child_started)
        return result.returncode

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
