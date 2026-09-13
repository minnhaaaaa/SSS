from __future__ import annotations

from pathlib import Path

import pytest
from sss_cli.adapters import GuardDecisionResult
from sss_cli.guard import GuardRunner, parse_install_argv
from sss_cli.process import ProcessResult
from sss_core import Decision, EvidenceScores


def test_parse_pnpm_add_builds_exact_guard_request() -> None:
    requests = parse_install_argv(
        "pnpm",
        ("add", "@sss-demo/reserved-synthetic@1.0.0"),
        registry_origin="https://npm.demo.sss.test",
        project_id="project-demo",
        agent_family="codex",
        artifact_sha256="b" * 64,
    )

    assert len(requests) == 1
    request = requests[0]
    assert request.package.canonical_name == "@sss-demo/reserved-synthetic"
    assert request.package.registry_origin == "https://npm.demo.sss.test"
    assert request.version_spec == "1.0.0"
    assert request.project_id == "project-demo"
    assert request.agent_family == "codex"
    assert request.artifact_sha256 == "b" * 64


@pytest.mark.parametrize(
    ("manager", "arguments", "expected_name", "expected_version", "expected_ecosystem"),
    [
        ("npm", ("install", "left-pad@1.3.0"), "left-pad", "1.3.0", "npm"),
        ("yarn", ("add", "left-pad@1.3.0"), "left-pad", "1.3.0", "npm"),
        ("npx", ("prettier@3.6.2",), "prettier", "3.6.2", "npm"),
        ("pip", ("install", "requests==2.32.5"), "requests", "==2.32.5", "pypi"),
        ("pip3", ("install", "requests==2.32.5"), "requests", "==2.32.5", "pypi"),
        (
            "python",
            ("-m", "pip", "install", "requests==2.32.5"),
            "requests",
            "==2.32.5",
            "pypi",
        ),
        ("uv", ("add", "requests==2.32.5"), "requests", "==2.32.5", "pypi"),
        ("uv", ("pip", "install", "requests==2.32.5"), "requests", "==2.32.5", "pypi"),
    ],
)
def test_supported_managers_build_policy_requests(
    manager: str,
    arguments: tuple[str, ...],
    expected_name: str,
    expected_version: str,
    expected_ecosystem: str,
) -> None:
    request = parse_install_argv(
        manager,
        arguments,
        registry_origin="https://registry.npmjs.org",
        pypi_registry_origin="https://pypi.org",
        project_id="project-test",
        agent_family="test-agent",
        artifact_sha256="a" * 64,
    )[0]

    assert request.package.canonical_name == expected_name
    assert request.package.ecosystem.value == expected_ecosystem
    assert request.version_spec == expected_version


@pytest.mark.parametrize(
    "arguments",
    [
        ("add", "@sss-demo/reserved-synthetic"),
        ("add", "https://attacker.test/package.tgz"),
        ("add", "github:attacker/package"),
        ("add", "../package"),
        ("add", "safe@1.0.0", "--registry=https://attacker.test"),
    ],
)
def test_parse_pnpm_add_rejects_ambiguous_or_nonregistry_sources(
    arguments: tuple[str, ...],
) -> None:
    with pytest.raises(ValueError):
        parse_install_argv(
            "pnpm",
            arguments,
            registry_origin="https://npm.demo.sss.test",
            project_id="project-demo",
            agent_family="codex",
            artifact_sha256="b" * 64,
        )


class AllowingGuardClient:
    def check(self, request: object) -> GuardDecisionResult:
        return GuardDecisionResult(
            decision_id="decision-allow",
            decision=Decision.ALLOW,
            reason_codes=("ESTABLISHED_APPROVED",),
            scores=EvidenceScores(100, 0, 0),
            policy_version="sss-hackathon-v3",
            intervention_id=None,
            child_process_allowed=True,
        )

    def record_attempt(self, **payload: object) -> None:
        self.attempt = payload


class RecordingProcessRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[str, ...], Path]] = []

    def run(
        self,
        manager: str,
        arguments: tuple[str, ...],
        *,
        cwd: Path,
        env: dict[str, str],
    ) -> ProcessResult:
        self.calls.append((manager, arguments, cwd))
        return ProcessResult(returncode=0, child_started=True)


def test_allow_starts_real_manager_once_with_original_argv(tmp_path: Path) -> None:
    process = RecordingProcessRunner()
    runner = GuardRunner(
        client=AllowingGuardClient(),
        process_runner=process,
        registry_origin="https://npm.demo.sss.test",
        project_id="project-demo",
        agent_family="codex",
        artifact_sha256="b" * 64,
        cwd=tmp_path,
        environment={},
        write=lambda _line: None,
    )

    result = runner.run("pnpm", ("add", "safe@1.0.0"))

    assert result == 0
    assert process.calls == [("pnpm", ("add", "safe@1.0.0"), tmp_path)]
