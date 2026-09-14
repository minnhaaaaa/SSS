from __future__ import annotations

import hashlib

import httpx
import pytest
from sss_gateway.config import GatewaySettings
from sss_gateway.main import create_app
from sss_gateway.policy import GatewayPermitSet
from sss_gateway.upstream import RegistryUpstreamClient


def _settings(*, max_bytes: int = 1024) -> GatewaySettings:
    return GatewaySettings.from_env(
        {
            "SSS_GATEWAY_UPSTREAMS_JSON": '{"npm":"https://registry.example.test"}',
            "SSS_GATEWAY_MAX_ARTIFACT_BYTES": str(max_bytes),
        }
    )


def _app(
    handler: httpx.MockTransport,
    permits: dict[str, dict[str, str | None]],
    *,
    max_bytes: int = 1024,
):
    settings = _settings(max_bytes=max_bytes)
    upstream = RegistryUpstreamClient(
        settings,
        client=httpx.AsyncClient(transport=handler),
    )
    return create_app(
        settings=settings,
        upstream=upstream,
        permits=GatewayPermitSet(permits),
    )


@pytest.mark.asyncio
async def test_exactly_permitted_metadata_and_artifact_are_proxied() -> None:
    artifact = b"safe-package-bytes"
    calls: list[str] = []

    def upstream(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/safe-lib":
            return httpx.Response(200, json={"name": "safe-lib"})
        return httpx.Response(200, content=artifact, headers={"content-type": "application/gzip"})

    app = _app(
        httpx.MockTransport(upstream),
        {
            "npm": {
                "/safe-lib": None,
                "/safe-lib/-/safe-lib-1.0.0.tgz": hashlib.sha256(artifact).hexdigest(),
            }
        },
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://gateway"
    ) as client:
        metadata = await client.get("/npm/safe-lib")
        package = await client.get("/npm/safe-lib/-/safe-lib-1.0.0.tgz")

    assert metadata.status_code == 200
    assert metadata.json() == {"name": "safe-lib"}
    assert package.status_code == 200
    assert package.content == artifact
    assert package.headers["x-content-sha256"] == hashlib.sha256(artifact).hexdigest()
    assert calls == ["/safe-lib", "/safe-lib/-/safe-lib-1.0.0.tgz"]


@pytest.mark.asyncio
async def test_encoded_scoped_npm_identity_is_not_rewritten() -> None:
    observed: list[str] = []

    def upstream(request: httpx.Request) -> httpx.Response:
        observed.append(request.url.raw_path.decode("ascii"))
        return httpx.Response(200, json={"name": "@scope/safe-lib"})

    app = _app(
        httpx.MockTransport(upstream),
        {"npm": {"/%40scope%2Fsafe-lib": None}},
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://gateway"
    ) as client:
        response = await client.get("/npm/%40scope%2Fsafe-lib")

    assert response.status_code == 200
    assert observed == ["/%40scope%2Fsafe-lib"]


@pytest.mark.asyncio
async def test_unknown_or_blocked_path_never_reaches_upstream() -> None:
    calls = 0

    def upstream(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, content=b"must-not-be-read")

    app = _app(httpx.MockTransport(upstream), {"npm": {"/safe-lib": None}})
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://gateway"
    ) as client:
        blocked_transitive = await client.get("/npm/unknown/-/unknown-1.0.0.tgz")
        query_smuggling = await client.get("/npm/safe-lib?registry=https://attacker.test")
        unknown_origin = await client.get("/attacker/safe-lib")

    assert blocked_transitive.status_code == 403
    assert query_smuggling.status_code == 400
    assert unknown_origin.status_code == 403
    assert calls == 0


@pytest.mark.asyncio
async def test_bad_digest_and_oversized_artifact_fail_closed() -> None:
    def upstream(request: httpx.Request) -> httpx.Response:
        body = b"wrong" if "wrong" in request.url.path else b"0123456789"
        return httpx.Response(200, content=body)

    app = _app(
        httpx.MockTransport(upstream),
        {
            "npm": {
                "/wrong/-/wrong-1.0.0.tgz": "a" * 64,
                "/large/-/large-1.0.0.tgz": "b" * 64,
            }
        },
        max_bytes=5,
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://gateway"
    ) as client:
        wrong = await client.get("/npm/wrong/-/wrong-1.0.0.tgz")
        large = await client.get("/npm/large/-/large-1.0.0.tgz")

    assert wrong.status_code == 502
    assert wrong.content == b'{"detail":"artifact digest mismatch"}'
    assert large.status_code == 413
