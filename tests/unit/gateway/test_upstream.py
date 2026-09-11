from __future__ import annotations

import httpx
import pytest
from sss_gateway.artifacts import ArchiveLimits
from sss_gateway.config import GatewaySettings
from sss_gateway.upstream import (
    RegistryUpstreamClient,
    UnknownUpstreamError,
    UpstreamRedirectError,
)


def _settings() -> GatewaySettings:
    return GatewaySettings(
        upstreams={"npm": "https://registry.example.test"},
        max_artifact_bytes=100,
        archive_limits=ArchiveLimits(100, 200, 10, 50, 20),
        connect_timeout_seconds=1,
        read_timeout_seconds=2,
    )


@pytest.mark.asyncio
async def test_upstream_client_only_reads_configured_origin_and_path() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"name": "package"})

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = RegistryUpstreamClient(_settings(), client=http_client)

    async with client.open("npm", "/%40scope%2Fpackage", accept="application/json") as response:
        assert response.status_code == 200
        await response.aread()

    assert requests[0].url == "https://registry.example.test/%40scope%2Fpackage"
    assert requests[0].headers["Accept"] == "application/json"
    await http_client.aclose()


@pytest.mark.asyncio
async def test_upstream_client_rejects_unknown_name_before_network() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200)

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = RegistryUpstreamClient(_settings(), client=http_client)

    with pytest.raises(UnknownUpstreamError):
        async with client.open("unapproved", "/package"):
            pass

    assert calls == 0
    await http_client.aclose()


@pytest.mark.asyncio
async def test_upstream_client_does_not_follow_redirects() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": "https://attacker.example/file"})

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = RegistryUpstreamClient(_settings(), client=http_client)

    with pytest.raises(UpstreamRedirectError):
        async with client.open("npm", "/package"):
            pass

    await http_client.aclose()
