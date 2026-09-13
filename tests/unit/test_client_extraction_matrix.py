from __future__ import annotations

import pytest
from sss_core.extraction.npm import extract_npm_mentions
from sss_core.extraction.python import extract_python_mentions


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("pip install Requests==2.32", ("requests", "==2.32")),
        ("pip3 install Requests==2.32", ("requests", "==2.32")),
        ("python -m pip install Requests==2.32", ("requests", "==2.32")),
        ("uv add Requests==2.32", ("requests", "==2.32")),
        ("uv pip install Requests==2.32", ("requests", "==2.32")),
    ],
)
def test_python_client_matrix(command: str, expected: tuple[str, str]) -> None:
    mentions = extract_python_mentions(command)

    assert [(mention.canonical_name, mention.version_spec) for mention in mentions] == [expected]


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("npm install react@19", ("react", "19")),
        ("pnpm add react@19", ("react", "19")),
        ("yarn add react@19", ("react", "19")),
        ("npx --yes react@19", ("react", "19")),
    ],
)
def test_npm_ecosystem_client_matrix(command: str, expected: tuple[str, str]) -> None:
    mentions = extract_npm_mentions(command)

    assert [(mention.canonical_name, mention.version_spec) for mention in mentions] == [expected]
