from __future__ import annotations

import pytest
from sss_core.domain import Ecosystem
from sss_core.identity import IdentityValidationError, canonicalize_identity


def test_pypi_name_uses_pep_503_normalization() -> None:
    identity = canonicalize_identity(
        Ecosystem.PYPI,
        "https://pypi.org/simple",
        "Django_REST.Framework",
    )

    assert identity.canonical_name == "django-rest-framework"
    assert identity.registry_origin == "https://pypi.org"


def test_npm_scoped_name_is_lowercase_and_preserves_scope() -> None:
    identity = canonicalize_identity(
        Ecosystem.NPM,
        "https://registry.npmjs.org/",
        "@Scope/Thing",
    )

    assert identity.canonical_name == "@scope/thing"
    assert identity.registry_origin == "https://registry.npmjs.org"


def test_identical_names_remain_distinct_across_ecosystems() -> None:
    pypi = canonicalize_identity(Ecosystem.PYPI, "https://pypi.org", "requests")
    npm = canonicalize_identity(Ecosystem.NPM, "https://registry.npmjs.org", "requests")

    assert pypi != npm


@pytest.mark.parametrize(
    "origin",
    [
        "http://registry.npmjs.org",
        "https://user:password@registry.npmjs.org",
        "https://registry.npmjs.org/#fragment",
        "https://registry.npmjs.org/path",
    ],
)
def test_registry_origin_rejects_unsafe_or_non_origin_urls(origin: str) -> None:
    with pytest.raises(IdentityValidationError):
        canonicalize_identity(Ecosystem.NPM, origin, "package")


@pytest.mark.parametrize(
    "name",
    ["", "UPPERCASE", "@scope", "@scope/", "scope/name", "@scope/name/extra", "bad name"],
)
def test_npm_name_validation_rejects_invalid_syntax(name: str) -> None:
    with pytest.raises(IdentityValidationError):
        canonicalize_identity(Ecosystem.NPM, "https://registry.npmjs.org", name)
