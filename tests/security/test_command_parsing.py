from __future__ import annotations

import pytest
from sss_core.extraction import UnsafeInputError
from sss_core.extraction.npm import extract_npm_mentions
from sss_core.extraction.python import extract_python_mentions


@pytest.mark.parametrize(
    "payload",
    [
        "pip install safe; touch /tmp/pwned",
        "pip install safe && whoami",
        "pip install safe | sh",
        "pip install safe > output",
        "pip install $(whoami)",
        "pip install `whoami`",
    ],
)
def test_python_shell_operators_are_rejected(payload: str) -> None:
    with pytest.raises(UnsafeInputError):
        extract_python_mentions(payload)


@pytest.mark.parametrize(
    "payload",
    [
        "npm install safe; touch /tmp/pwned",
        "pnpm add safe && whoami",
        "yarn add safe | sh",
        "npx safe < input",
        "npm install $(whoami)",
        "npm install `whoami`",
    ],
)
def test_npm_shell_operators_are_rejected(payload: str) -> None:
    with pytest.raises(UnsafeInputError):
        extract_npm_mentions(payload)
