"""Reject unsafe or ambiguous upstream request paths."""

from __future__ import annotations

import re
from urllib.parse import unquote


class UnsafeGatewayPath(ValueError):
    """Raised for a path that must never reach an upstream registry."""


_MALFORMED_PERCENT = re.compile(r"%(?![0-9A-Fa-f]{2})")


def validate_gateway_path(value: str) -> str:
    if not value.startswith("/") or value.startswith("//"):
        raise UnsafeGatewayPath("gateway path must be a single-root absolute path")
    if "\\" in value or any(ord(character) < 32 for character in value):
        raise UnsafeGatewayPath("gateway path contains forbidden characters")
    if "?" in value or "#" in value:
        raise UnsafeGatewayPath("gateway path cannot contain a query or fragment")
    if _MALFORMED_PERCENT.search(value):
        raise UnsafeGatewayPath("gateway path contains malformed percent encoding")

    decoded = value
    for _decode_pass in range(4):
        previous = decoded
        decoded = unquote(decoded)
        if any(character in decoded for character in ("\\", "?", "#")) or any(
            ord(character) < 32 for character in decoded
        ):
            raise UnsafeGatewayPath("gateway path contains encoded forbidden characters")
        segments = decoded.split("/")
        if any(segment in {".", ".."} for segment in segments):
            raise UnsafeGatewayPath("gateway path contains traversal")
        if "//" in decoded:
            raise UnsafeGatewayPath("gateway path contains an empty segment")
        if decoded == previous:
            break
    if "%" in decoded:
        raise UnsafeGatewayPath("gateway path contains excessive percent encoding")
    return value
