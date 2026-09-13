from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest
from sss_cli.process import ProcessConfigurationError, SafeProcessRunner


class RecordingBackend:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[str, ...], Path, dict[str, str]]] = []

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str],
    ) -> int:
        self.calls.append((tuple(argv), cwd, dict(env)))
        return 0


def test_runner_uses_configured_absolute_executable_and_original_argv(tmp_path: Path) -> None:
    backend = RecordingBackend()
    executable = tmp_path / "pnpm"
    executable.touch()
    runner = SafeProcessRunner(executables={"pnpm": executable}, backend=backend)

    result = runner.run("pnpm", ["add", "example@1.0.0"], cwd=tmp_path, env={"PATH": "/safe"})

    assert result.child_started is True
    assert backend.calls == [
        ((str(executable), "add", "example@1.0.0"), tmp_path, {"PATH": "/safe"})
    ]


def test_runner_rejects_unknown_manager_without_starting_child(tmp_path: Path) -> None:
    backend = RecordingBackend()
    runner = SafeProcessRunner(executables={}, backend=backend)

    with pytest.raises(ProcessConfigurationError, match="no immutable executable"):
        runner.run("pnpm", ["add", "example"], cwd=tmp_path, env={})

    assert backend.calls == []
