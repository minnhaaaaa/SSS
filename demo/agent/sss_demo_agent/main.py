"""A deterministic agent that delegates one package install to the protected boundary."""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Mapping, Sequence
from os import environ
from typing import Protocol

DEMO_PACKAGE = "@sss-demo/reserved-synthetic@1.0.0"


class AgentProcessBackend(Protocol):
    def run(self, argv: Sequence[str], *, env: Mapping[str, str]) -> int: ...


class SubprocessAgentBackend:
    def run(self, argv: Sequence[str], *, env: Mapping[str, str]) -> int:
        completed = subprocess.run(  # noqa: S603 - fixed executable and argument vector.
            list(argv),
            env=dict(env),
            check=False,
            shell=False,
        )
        return completed.returncode


def run_agent(
    *,
    backend: AgentProcessBackend | None = None,
    environment: Mapping[str, str] = environ,
    write: Callable[[str], None] = print,
) -> int:
    write("Demo agent: running a controlled fixture task.")
    write("Demo agent: dependency looks useful; delegating installation to pnpm.")
    process = backend or SubprocessAgentBackend()
    return process.run(("pnpm", "add", DEMO_PACKAGE), env=environment)


def main() -> None:
    raise SystemExit(run_agent())


if __name__ == "__main__":
    main()
