"""Connectivity checks that do not require domain or policy contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True, slots=True)
class ServiceCheck:
    name: str
    healthy: bool
    detail: str


def check_http_service(
    name: str,
    base_url: str,
    *,
    timeout_seconds: float = 3.0,
    client: httpx.Client | None = None,
) -> ServiceCheck:
    try:
        request = client.get if client is not None else httpx.get
        response = request(f"{base_url.rstrip('/')}/health/live", timeout=timeout_seconds)
        response.raise_for_status()
        payload: Any = response.json()
        if not isinstance(payload, dict) or payload.get("status") != "ok":
            return ServiceCheck(name=name, healthy=False, detail="invalid health response")
    except (httpx.HTTPError, ValueError) as exc:
        return ServiceCheck(name=name, healthy=False, detail=str(exc))
    return ServiceCheck(name=name, healthy=True, detail=f"HTTP {response.status_code}")
