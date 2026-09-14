"""Fail-closed package-registry gateway composition."""

from __future__ import annotations

import hmac

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import Response

from sss_gateway.config import GatewaySettings
from sss_gateway.policy import GatewayPermitSet
from sss_gateway.security.paths import UnsafeGatewayPath, validate_gateway_path
from sss_gateway.streaming import ArtifactTooLargeError, BoundedHashingStream
from sss_gateway.upstream import (
    RegistryUpstreamClient,
    UnknownUpstreamError,
    UpstreamRedirectError,
)


def create_app(
    *,
    settings: GatewaySettings | None = None,
    upstream: RegistryUpstreamClient | None = None,
    permits: GatewayPermitSet | None = None,
) -> FastAPI:
    resolved = settings or GatewaySettings.from_env()
    upstream_client = upstream or RegistryUpstreamClient(resolved)
    permit_set = permits or GatewayPermitSet.from_env()
    app = FastAPI(title="SSS Registry Gateway", version="0.2.0")
    app.state.settings = resolved
    app.state.upstream = upstream_client
    app.state.permits = permit_set

    @app.get("/health/live", tags=["health"])
    async def live() -> dict[str, object]:
        return {
            "status": "ok",
            "service": "sss-gateway",
            "configured_upstreams": sorted(resolved.upstreams),
        }

    @app.get("/{upstream_name}/{path:path}", tags=["registry"])
    async def proxy(upstream_name: str, path: str, request: Request) -> Response:
        if request.url.query:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="query parameters are not accepted by the registry gateway",
            )
        try:
            del path  # The decoded route value is unsafe for encoded npm scopes.
            raw_segments = request.scope["raw_path"].split(b"/", 2)
            if len(raw_segments) != 3:
                raise UnsafeGatewayPath("gateway path is missing")
            try:
                raw_path = b"/" + raw_segments[2]
                safe_path = validate_gateway_path(raw_path.decode("ascii"))
            except UnicodeDecodeError as exc:
                raise UnsafeGatewayPath("gateway path must be ASCII encoded") from exc
            permit = permit_set.authorize(upstream_name, safe_path)
            async with upstream_client.open(
                upstream_name,
                safe_path,
                accept=request.headers.get("accept"),
            ) as upstream_response:
                if upstream_response.status_code >= 400:
                    mapped_status = (
                        upstream_response.status_code
                        if upstream_response.status_code in {404, 410}
                        else status.HTTP_502_BAD_GATEWAY
                    )
                    raise HTTPException(status_code=mapped_status, detail="registry read failed")
                stream = BoundedHashingStream(
                    upstream_response.aiter_bytes(), max_bytes=resolved.max_artifact_bytes
                )
                chunks = [chunk async for chunk in stream]
                digest = stream.sha256
                if permit.expected_sha256 is not None and not hmac.compare_digest(
                    digest, permit.expected_sha256
                ):
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="artifact digest mismatch",
                    )
                headers = {"X-Content-SHA256": digest, "X-Content-Type-Options": "nosniff"}
                content_type = upstream_response.headers.get("content-type")
                if content_type:
                    headers["Content-Type"] = content_type
                return Response(content=b"".join(chunks), headers=headers)
        except UnsafeGatewayPath as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except (PermissionError, UnknownUpstreamError) as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ArtifactTooLargeError as exc:
            raise HTTPException(status_code=413, detail=str(exc)) from exc
        except UpstreamRedirectError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    return app
