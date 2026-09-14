from __future__ import annotations

from pathlib import Path

from sss_cli.adapters import GuardDecisionResult
from sss_cli.guard import BLOCK_EXIT_CODE, GuardRunner
from sss_cli.process import ProcessResult
from sss_core import Decision, EvidenceScores


class BlockingGuardClient:
    def __init__(self) -> None:
        self.attempts: list[dict[str, object]] = []

    def check(self, request: object) -> GuardDecisionResult:
        return GuardDecisionResult(
            decision_id="decision-block",
            decision=Decision.BLOCK,
            reason_codes=(
                "REGISTERED_AFTER_HALLUCINATION",
                "HIGH_GLOBAL_RECURRENCE",
            ),
            scores=EvidenceScores(100, 95, 75),
            policy_version="sss-hackathon-v3",
            intervention_id="intervention-block",
            child_process_allowed=False,
        )

    def record_attempt(self, **payload: object) -> None:
        self.attempts.append(dict(payload))


class ForbiddenProcessRunner:
    def __init__(self) -> None:
        self.calls = 0

    def run(
        self,
        manager: str,
        arguments: tuple[str, ...],
        *,
        cwd: Path,
        env: dict[str, str],
    ) -> ProcessResult:
        self.calls += 1
        raise AssertionError("blocked package manager must never start")


def test_block_returns_23_records_nonexecution_and_starts_zero_children(
    tmp_path: Path,
) -> None:
    client = BlockingGuardClient()
    process = ForbiddenProcessRunner()
    output: list[str] = []
    runner = GuardRunner(
        client=client,
        process_runner=process,
        registry_origin="https://npm.demo.sss.test",
        project_id="project-demo",
        agent_family="codex",
        artifact_sha256="b" * 64,
        cwd=tmp_path,
        environment={},
        write=output.append,
    )

    result = runner.run("pnpm", ("add", "@sss-demo/reserved-synthetic@1.0.0"))

    assert result == BLOCK_EXIT_CODE == 23
    assert process.calls == 0
    assert client.attempts == [
        {
            "decision_id": "decision-block",
            "manager": "pnpm",
            "arguments": ("add", "@sss-demo/reserved-synthetic@1.0.0"),
            "agent_family": "codex",
            "project_id": "project-demo",
            "decision": "block",
            "child_started": False,
        }
    ]
    rendered = "\n".join(output)
    assert "Absence confidence: 100" in rendered
    assert "Target attractiveness: 95" in rendered
    assert "Package policy risk: 75" in rendered
    assert "Installation was not started." in rendered
    assert "intervention-block" in rendered
