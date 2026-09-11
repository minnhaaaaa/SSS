"""Allowlisted registry reads with redirects disabled."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager

import httpx

from sss_gateway.config import GatewaySettings
from sss_gateway.security.paths import validate_gateway_path


class UnknownUpstreamError(ValueError):
    """Raised when a request names an upstream not present in configuration."""


class UpstreamRedirectError(ValueError):
    """Raised because registry redirects require a separate policy decision."""


class RegistryUpstreamClient:
    def __init__(
        self,
        settings: GatewaySettings,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            follow_redirects=False,
            timeout=httpx.Timeout(
                connect=settings.connect_timeout_seconds,
                read=settings.read_timeout_seconds,
                write=settings.read_timeout_seconds,
                pool=settings.connect_timeout_seconds,
            ),
        )

    @asynccontextmanager
    async def open(
        self,
        upstream_name: str,
        path: str,
        *,
        accept: str | None = None,
    ) -> AsyncIterator[httpx.Response]:
        origin = self._settings.upstreams.get(upstream_name.casefold())
        if origin is None:
            raise UnknownUpstreamError(f"unknown registry upstream: {upstream_name}")
        safe_path = validate_gateway_path(path)
        headers: Mapping[str, str] = {"Accept": accept} if accept else {}
        async with self._client.stream("GET", f"{origin}{safe_path}", headers=headers) as response:
            if response.is_redirect:
                raise UpstreamRedirectError("registry redirect requires explicit validation")
            yield response

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()
