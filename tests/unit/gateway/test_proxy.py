from __future__ import annotations

import httpx
import pytest
from sss_gateway.artifacts import ArchiveLimits
from sss_gateway.config import GatewaySettings
from sss_gateway.main import create_app
from sss_gateway.upstream import RegistryUpstreamClient


def _settings(*, max_bytes: int = 100) -> GatewaySettings:
    return GatewaySettings(
        upstreams={
            "npm": "https://registry.example.test",
            "pypi": "https://pypi.example.test",
            "pypi-files": "https://files.example.test",
        },
        max_artifact_bytes=max_bytes,
        archive_limits=ArchiveLimits(max_bytes, 200, 10, 50, 20),
        connect_timeout_seconds=1,
        read_timeout_seconds=2,
    )


@pytest.mark.asyncio
async def test_proxy_returns_bounded_metadata_with_digest() -> None:
    settings = _settings()
    upstream_http = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                content=(
                    b'{"name":"left-pad","dist":{"tarball":'
                    b'"https://registry.example.test/left-pad/-/left-pad-1.3.0.tgz"}}'
                ),
                headers={"Content-Type": "application/json"},
            )
        )
    )
    upstream = RegistryUpstreamClient(settings, client=upstream_http)
    transport = httpx.ASGITransport(app=create_app(settings=settings, upstream_client=upstream))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/registry/npm/left-pad")

    assert response.status_code == 200
    assert response.json() == {
        "name": "left-pad",
        "dist": {"tarball": "http://test/v1/registry/npm/left-pad/-/left-pad-1.3.0.tgz"},
    }
    assert len(response.headers["X-SSS-Upstream-SHA256"]) == 64
    await upstream_http.aclose()


@pytest.mark.asyncio
async def test_proxy_rejects_unknown_registry_without_network() -> None:
    settings = _settings()
    upstream_http = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(500))
    )
    upstream = RegistryUpstreamClient(settings, client=upstream_http)
    transport = httpx.ASGITransport(app=create_app(settings=settings, upstream_client=upstream))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/registry/unapproved/simple/requests")

    assert response.status_code == 404
    await upstream_http.aclose()


@pytest.mark.asyncio
async def test_proxy_rewrites_allowlisted_pypi_artifact_links() -> None:
    settings = _settings(max_bytes=500)
    upstream_http = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                content=(
                    b'<a href="https://files.example.test/packages/request-1.0.whl">request</a>'
                ),
                headers={"Content-Type": "text/html"},
            )
        )
    )
    upstream = RegistryUpstreamClient(settings, client=upstream_http)
    transport = httpx.ASGITransport(app=create_app(settings=settings, upstream_client=upstream))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/registry/pypi/simple/requests")

    assert "http://test/v1/registry/pypi-files/packages/request-1.0.whl" in response.text
    await upstream_http.aclose()
