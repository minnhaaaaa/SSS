from __future__ import annotations

from pathlib import Path

import pytest
from sss_cli.adapters import GuardAdapterError, GuardDecisionResult
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
        self.environments: list[dict[str, str]] = []

    def run(
        self,
        manager: str,
        arguments: tuple[str, ...],
        *,
        cwd: Path,
        env: dict[str, str],
    ) -> ProcessResult:
        self.calls.append((manager, arguments, cwd))
        self.environments.append(dict(env))
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


class ApprovedRetryGuardClient:
    def __init__(self) -> None:
        self.consumed: list[tuple[str, str, str]] = []
        self.attempts: list[dict[str, object]] = []

    def check(self, request: object) -> GuardDecisionResult:
        return GuardDecisionResult(
            decision_id="decision-block",
            decision=Decision.BLOCK,
            reason_codes=("REGISTERED_AFTER_HALLUCINATION",),
            scores=EvidenceScores(100, 95, 75),
            policy_version="sss-hackathon-v3",
            intervention_id="intervention-block",
            child_process_allowed=False,
        )

    def consume_approval(self, *, token: str, request_id: str, nonce: str) -> str:
        self.consumed.append((token, request_id, nonce))
        return "approval-one"

    def record_attempt(self, **payload: object) -> None:
        self.attempts.append(dict(payload))


def test_exact_approved_retry_consumes_once_and_scrubs_grant_from_child(
    tmp_path: Path,
) -> None:
    client = ApprovedRetryGuardClient()
    process = RecordingProcessRunner()
    runner = GuardRunner(
        client=client,
        process_runner=process,
        registry_origin="https://npm.demo.sss.test",
        project_id="project-demo",
        agent_family="codex",
        artifact_sha256="b" * 64,
        cwd=tmp_path,
        environment={
            "PATH": "/safe/bin",
            "SSS_APPROVAL_TOKEN": "signed-one-use-token",
            "SSS_APPROVAL_NONCE": "nonce-one",
        },
        write=lambda _line: None,
    )

    result = runner.run("pnpm", ("add", "@sss-demo/reserved-synthetic@1.0.0"))

    assert result == 0
    assert len(client.consumed) == 1
    assert client.consumed[0][0::2] == ("signed-one-use-token", "nonce-one")
    assert process.calls == [
        ("pnpm", ("add", "@sss-demo/reserved-synthetic@1.0.0"), tmp_path)
    ]
    assert process.environments == [{"PATH": "/safe/bin"}]
    assert client.attempts[0]["decision"] == "allow"


def test_invalid_approval_retry_fails_closed_without_starting_child(tmp_path: Path) -> None:
    class InvalidApprovalClient(ApprovedRetryGuardClient):
        def consume_approval(self, *, token: str, request_id: str, nonce: str) -> str:
            raise GuardAdapterError("exact-scope approval could not be consumed")

    client = InvalidApprovalClient()
    process = RecordingProcessRunner()
    output: list[str] = []
    runner = GuardRunner(
        client=client,
        process_runner=process,
        registry_origin="https://npm.demo.sss.test",
        project_id="project-demo",
        agent_family="codex",
        artifact_sha256="b" * 64,
        cwd=tmp_path,
        environment={
            "SSS_APPROVAL_TOKEN": "invalid-or-reused",
            "SSS_APPROVAL_NONCE": "nonce-one",
        },
        write=output.append,
    )

    assert runner.run("pnpm", ("add", "@sss-demo/reserved-synthetic@1.0.0")) == 23
    assert process.calls == []
    assert "Installation was not started." in output
