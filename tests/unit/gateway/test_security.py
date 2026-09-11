from __future__ import annotations

import pytest
from sss_gateway.security.origins import normalize_origin
from sss_gateway.security.paths import UnsafeGatewayPath, validate_gateway_path


def test_origin_is_canonicalized() -> None:
    assert normalize_origin("https://REGISTRY.EXAMPLE.TEST/") == "https://registry.example.test"


@pytest.mark.parametrize(
    "value",
    [
        "http://registry.example.test",
        "https://user:secret@registry.example.test",
        "https://registry.example.test/path",
        "https://registry.example.test?query=yes",
    ],
)
def test_origin_rejects_unsafe_values(value: str) -> None:
    with pytest.raises(ValueError):
        normalize_origin(value)


@pytest.mark.parametrize(
    "value",
    [
        "/../secret",
        "/%2e%2e/secret",
        "/%252e%252e/secret",
        "//host/path",
        "/a\\b",
        "/a%5cb",
        "/package%0dheader",
        "/malformed%2",
        "/package?redirect=https://attacker.example",
        "/package#fragment",
    ],
)
def test_gateway_path_rejects_ambiguous_or_traversing_values(value: str) -> None:
    with pytest.raises(UnsafeGatewayPath):
        validate_gateway_path(value)


def test_gateway_path_preserves_safe_encoded_scope() -> None:
    assert validate_gateway_path("/%40scope%2Fpackage") == "/%40scope%2Fpackage"
