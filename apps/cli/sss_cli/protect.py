"""Docker Compose launcher for an unprivileged protected session."""

from __future__ import annotations

import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


class LauncherBackend(Protocol):
    def run(self, argv: Sequence[str], *, env: Mapping[str, str]) -> int: ...


class DockerBackend:
    def run(self, argv: Sequence[str], *, env: Mapping[str, str]) -> int:
        result = subprocess.run(  # noqa: S603 - argv is constructed without a shell.
            list(argv), env=dict(env), shell=False, check=False
        )
        return result.returncode


@dataclass(frozen=True, slots=True)
class ProtectedLauncher:
    docker_executable: str
    compose_file: Path
    service: str
    backend: LauncherBackend = field(default_factory=DockerBackend)

    def launch(self, command: Sequence[str], *, environment: Mapping[str, str]) -> int:
        if not command:
            raise ValueError("a protected command is required")
        if not self.compose_file.is_file():
            raise ValueError(f"compose file does not exist: {self.compose_file}")
        if any("\x00" in item or "\r" in item or "\n" in item for item in command):
            raise ValueError("protected command contains invalid control characters")
        argv = [
            self.docker_executable,
            "compose",
            "-f",
            str(self.compose_file),
            "run",
            "--rm",
            self.service,
            *command,
        ]
        return self.backend.run(argv, env=environment)
