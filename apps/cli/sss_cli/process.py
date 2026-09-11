"""Safe, injectable child-process execution primitives."""

from __future__ import annotations

import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class ProcessConfigurationError(ValueError):
    """Raised before any child starts when execution inputs are invalid."""


@dataclass(frozen=True, slots=True)
class ProcessResult:
    returncode: int
    child_started: bool


class ProcessBackend(Protocol):
    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str],
    ) -> int: ...


class SubprocessBackend:
    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str],
    ) -> int:
        completed = subprocess.run(  # noqa: S603 - argv is an explicit sequence; shell is disabled.
            list(argv),
            cwd=cwd,
            env=dict(env),
            check=False,
            shell=False,
        )
        return completed.returncode


class SafeProcessRunner:
    def __init__(
        self,
        *,
        executables: Mapping[str, Path],
        backend: ProcessBackend | None = None,
    ) -> None:
        self._executables = {name.casefold(): path for name, path in executables.items()}
        self._backend = backend or SubprocessBackend()

    def run(
        self,
        manager: str,
        arguments: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str],
    ) -> ProcessResult:
        executable = self._executables.get(manager.casefold())
        if executable is None:
            raise ProcessConfigurationError(f"no immutable executable configured for {manager!r}")
        if not executable.is_absolute():
            raise ProcessConfigurationError("configured executable must be absolute")
        if not executable.is_file():
            raise ProcessConfigurationError("configured executable does not exist")
        if not cwd.is_absolute():
            raise ProcessConfigurationError("working directory must be absolute")
        if any(
            "\x00" in argument or "\r" in argument or "\n" in argument for argument in arguments
        ):
            raise ProcessConfigurationError("arguments contain invalid control characters")
        returncode = self._backend.run([str(executable), *arguments], cwd=cwd, env=env)
        return ProcessResult(returncode=returncode, child_started=True)
