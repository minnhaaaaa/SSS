from __future__ import annotations

from collections.abc import Mapping, Sequence

from sss_demo_agent.main import DEMO_PACKAGE, run_agent


class RecordingBackend:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[str, ...], bool]] = []

    def run(self, argv: Sequence[str], *, env: Mapping[str, str]) -> int:
        self.calls.append((tuple(argv), False))
        return 23


def test_controlled_agent_invokes_package_manager_boundary_once() -> None:
    backend = RecordingBackend()
    output: list[str] = []

    result = run_agent(backend=backend, environment={}, write=output.append)

    assert result == 23
    assert backend.calls == [
        (
            (
                "pnpm",
                "add",
                DEMO_PACKAGE,
                "--allow-build=@sss-demo/reserved-synthetic",
            ),
            False,
        )
    ]
    assert DEMO_PACKAGE == "@sss-demo/reserved-synthetic@1.0.0"
    assert any("controlled fixture" in line.lower() for line in output)
    assert any("delegating" in line.lower() for line in output)
