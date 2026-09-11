from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from sss_cli.protect import ProtectedLauncher


class RecordingLauncherBackend:
    def __init__(self) -> None:
        self.argv: tuple[str, ...] | None = None
        self.environment: dict[str, str] | None = None

    def run(self, argv: Sequence[str], *, env: Mapping[str, str]) -> int:
        self.argv = tuple(argv)
        self.environment = dict(env)
        return 7


def test_launcher_passes_command_as_argument_vector(tmp_path: Path) -> None:
    compose = tmp_path / "compose.yaml"
    compose.touch()
    backend = RecordingLauncherBackend()
    launcher = ProtectedLauncher(
        docker_executable="docker",
        compose_file=compose,
        service="protected-agent",
        backend=backend,
    )

    result = launcher.launch(["agent", "--non-interactive"], environment={"TERM": "xterm"})

    assert result == 7
    assert backend.argv == (
        "docker",
        "compose",
        "-f",
        str(compose),
        "run",
        "--rm",
        "protected-agent",
        "agent",
        "--non-interactive",
    )
