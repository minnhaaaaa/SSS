from __future__ import annotations

import pytest
from sss_api.idempotency import validate_idempotency_key


@pytest.mark.parametrize(
    "value",
    [
        "request-123",
        "123e4567-e89b-12d3-a456-426614174000",
        "client:operation_1.retry",
    ],
)
def test_idempotency_key_accepts_safe_opaque_tokens(value: str) -> None:
    assert validate_idempotency_key(value, max_bytes=128) == value


@pytest.mark.parametrize("value", ["", " leading", "contains space", "line\nbreak", "ü"])
def test_idempotency_key_rejects_ambiguous_values(value: str) -> None:
    with pytest.raises(ValueError):
        validate_idempotency_key(value, max_bytes=128)


def test_idempotency_key_applies_encoded_byte_limit() -> None:
    with pytest.raises(ValueError):
        validate_idempotency_key("a" * 129, max_bytes=128)
