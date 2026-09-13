"""Canonical approved-origin validation."""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit


def normalize_origin(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("registry upstream must be an absolute HTTPS origin")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("registry upstream cannot contain credentials, query, or fragment")
    if parsed.path not in {"", "/"}:
        raise ValueError("registry upstream must not include a path")
    host = parsed.hostname.casefold()
    port = f":{parsed.port}" if parsed.port is not None else ""
    return urlunsplit(("https", f"{host}{port}", "", "", ""))
