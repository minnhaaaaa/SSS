from __future__ import annotations

import pytest
from sss_cli.adapters import GuardAdapterError, GuardDecisionResult
from sss_cli.process import ProcessResult
from sss_cli.shim import run_shim
from sss_core import Decision, EvidenceScores

CLIENTS = (
    ("pip", ["install", "novel-lib==1.0.0"]),
    ("pip3", ["install", "novel-lib==1.0.0"]),
    ("python", ["-m", "pip", "install", "novel-lib==1.0.0"]),
    ("uv", ["add", "novel-lib==1.0.0"]),
    ("poetry", ["add", "novel-lib==1.0.0"]),
    ("npm", ["install", "novel-lib@1.0.0"]),
    ("pnpm", ["add", "novel-lib@1.0.0"]),
    ("yarn", ["add", "novel-lib@1.0.0"]),
    ("npx", ["novel-lib@1.0.0"]),
)


class RecordingProcess:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    def run(self, manager, arguments, *, cwd, env):  # type: ignore[no-untyped-def]
        self.calls.append((manager, tuple(arguments)))
        return ProcessResult(0, True)


class FixedGuard:
    def __init__(self, decision: Decision) -> None:
        self.decision = decision
        self.checks = 0
        self.attempts: list[dict[str, object]] = []

    def check(self, request):  # type: ignore[no-untyped-def]
        self.checks += 1
        return GuardDecisionResult(
            decision_id=f"decision-{self.checks}",
            decision=self.decision,
            reason_codes=("UNAUTHORIZED_PACKAGE",),
            scores=EvidenceScores(90, 80, 75),
            policy_version="policy-1",
            intervention_id="intervention-1",
            child_process_allowed=self.decision is Decision.ALLOW,
        )

    def record_attempt(self, **payload: object) -> None:
        self.attempts.append(payload)


class FailingGuard(FixedGuard):
    def check(self, request):  # type: ignore[no-untyped-def]
        del request
        raise GuardAdapterError("Guard assessment unavailable")


def environment() -> dict[str, str]:
    return {
        "SSS_API_URL": "https://api.example.test",
        "SSS_GATEWAY_URL": "https://gateway.example.test",
        "SSS_API_TOKEN": "test-token",
        "SSS_REAL_EXECUTABLES_JSON": "{}",
        "SSS_DEMO_ARTIFACT_SHA256": "b" * 64,
    }


@pytest.mark.parametrize(("client", "argv"), CLIENTS)
def test_blocked_client_never_starts_child(client: str, argv: list[str]) -> None:
    process = RecordingProcess()
    guard = FixedGuard(Decision.BLOCK)

    result = run_shim(
        client,
        argv,
        environment(),
        guard_client=guard,
        process_runner=process,
        write=lambda _line: None,
    )

    assert result == 23
    assert guard.checks == 1
    assert process.calls == []
    assert guard.attempts[0]["child_started"] is False


@pytest.mark.parametrize(("client", "argv"), CLIENTS)
def test_allowed_client_starts_original_argv_once(client: str, argv: list[str]) -> None:
    process = RecordingProcess()
    guard = FixedGuard(Decision.ALLOW)

    result = run_shim(
        client,
        argv,
        environment(),
        guard_client=guard,
        process_runner=process,
        write=lambda _line: None,
    )

    assert result == 0
    assert process.calls == [(client, tuple(argv))]


@pytest.mark.parametrize(
    ("client", "argv"),
    [
        ("pip", ["install", "https://attacker.test/pkg.whl"]),
        ("pip", ["install", "git+https://attacker.test/pkg.git"]),
        ("uv", ["add", "../pkg"]),
        ("npm", ["install", "https://attacker.test/pkg.tgz"]),
        ("pnpm", ["add", "pkg@1.0.0", "--registry=https://attacker.test"]),
        ("npx", ["pkg@1.0.0", "&&", "whoami"]),
    ],
)
def test_unsafe_sources_and_shell_tokens_fail_closed(
    client: str, argv: list[str]
) -> None:
    process = RecordingProcess()
    result = run_shim(
        client,
        argv,
        environment(),
        guard_client=FixedGuard(Decision.BLOCK),
        process_runner=process,
        write=lambda _line: None,
    )
    assert result == 23
    assert process.calls == []


def test_python_non_pip_command_is_delegated_as_an_argv_vector() -> None:
    process = RecordingProcess()
    result = run_shim(
        "python",
        ["-c", "print('semicolon; remains data')"],
        environment(),
        guard_client=FixedGuard(Decision.BLOCK),
        process_runner=process,
        write=lambda _line: None,
    )
    assert result == 0
    assert process.calls == [("python", ("-c", "print('semicolon; remains data')"))]


def test_missing_artifact_hash_fails_before_guard_or_child() -> None:
    values = environment()
    values["SSS_DEMO_ARTIFACT_SHA256"] = ""
    process = RecordingProcess()
    result = run_shim(
        "pnpm",
        ["add", "novel-lib@1.0.0"],
        values,
        guard_client=FixedGuard(Decision.ALLOW),
        process_runner=process,
        write=lambda _line: None,
    )
    assert result == 23
    assert process.calls == []


def test_guard_outage_fails_closed_without_starting_child() -> None:
    process = RecordingProcess()
    result = run_shim(
        "npm",
        ["install", "novel-lib@1.0.0"],
        environment(),
        guard_client=FailingGuard(Decision.ALLOW),
        process_runner=process,
        write=lambda _line: None,
    )
    assert result == 23
    assert process.calls == []


@pytest.mark.parametrize(
    ("client", "argv"),
    [
        ("npm", ["ci"]),
        ("pnpm", ["install"]),
        ("yarn", ["install"]),
        ("poetry", ["install"]),
        ("uv", ["sync"]),
        ("npx", ["--package", "novel-lib@1.0.0", "novel-lib"]),
    ],
)
def test_manifest_and_dynamic_install_forms_cannot_bypass_guard(
    client: str, argv: list[str]
) -> None:
    process = RecordingProcess()
    result = run_shim(
        client,
        argv,
        environment(),
        guard_client=FixedGuard(Decision.BLOCK),
        process_runner=process,
        write=lambda _line: None,
    )
    assert result == 23
    assert process.calls == []
