from __future__ import annotations

import pytest
from sss_cli.environment import UnsafeEnvironmentError, build_minimal_environment


def test_minimal_environment_excludes_unapproved_values_and_secrets() -> None:
    result = build_minimal_environment(
        {
            "PATH": "/safe/bin",
            "UNRELATED": "excluded",
            "SSS_APPROVAL_SIGNING_KEY": "must-not-leak",
        },
        allowed_keys=frozenset({"PATH", "SSS_APPROVAL_SIGNING_KEY"}),
    )

    assert result == {"PATH": "/safe/bin"}


def test_minimal_environment_rejects_secret_override() -> None:
    with pytest.raises(UnsafeEnvironmentError):
        build_minimal_environment(
            {},
            allowed_keys=frozenset(),
            overrides={"SSS_APPROVAL_SIGNING_KEY": "must-not-leak"},
        )
