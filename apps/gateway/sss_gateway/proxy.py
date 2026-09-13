"""Bounded, allowlisted registry proxy routes."""

from __future__ import annotations

import json
from collections.abc import Mapping
from io import BytesIO
from urllib.parse import quote

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import Response

from sss_gateway.artifacts import UnsafeArchiveError, inspect_tar, inspect_zip
from sss_gateway.security.paths import UnsafeGatewayPath
from sss_gateway.streaming import ArtifactTooLargeError, BoundedHashingStream
from sss_gateway.upstream import (
    RegistryUpstreamClient,
    UnknownUpstreamError,
    UpstreamRedirectError,
)

router = APIRouter(prefix="/v1/registry", tags=["registry"])
_PASSTHROUGH_HEADERS = ("content-type", "cache-control", "etag", "last-modified")


@router.get("/{upstream}/{resource_path:path}")
async def registry_resource(upstream: str, resource_path: str, request: Request) -> Response:
    """Return a registry resource only after bounded download and archive inspection."""

    client: RegistryUpstreamClient = request.app.state.upstream_client
    configured = request.app.state.settings.upstreams
    if upstream.casefold() not in configured:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown registry")
    path = "/" + quote(resource_path, safe="/@-._~")
    try:
        async with client.open(
            upstream,
            path,
            accept=request.headers.get("accept"),
        ) as upstream_response:
            body, digest = await _bounded_body(
                upstream_response,
                max_bytes=request.app.state.settings.max_artifact_bytes,
            )
            if _is_archive(resource_path):
                _inspect_archive(
                    resource_path,
                    body,
                    limits=request.app.state.settings.archive_limits,
                )
            else:
                body = _rewrite_metadata_links(
                    body,
                    content_type=upstream_response.headers.get("content-type", ""),
                    upstreams=configured,
                    gateway_origin=str(request.base_url).rstrip("/"),
                )
            headers = {
                name: upstream_response.headers[name]
                for name in _PASSTHROUGH_HEADERS
                if name in upstream_response.headers
            }
            headers["X-SSS-Upstream-SHA256"] = digest
            return Response(
                content=body,
                status_code=upstream_response.status_code,
                headers=headers,
                media_type=None,
            )
    except UnsafeGatewayPath as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except UnknownUpstreamError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ArtifactTooLargeError, UnsafeArchiveError) as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)
        ) from exc
    except (UpstreamRedirectError, httpx.HTTPError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="registry unavailable"
        ) from exc


async def _bounded_body(response: httpx.Response, *, max_bytes: int) -> tuple[bytes, str]:
    stream = BoundedHashingStream(response.aiter_bytes(), max_bytes=max_bytes)
    chunks = [chunk async for chunk in stream]
    return b"".join(chunks), stream.sha256


def _is_archive(path: str) -> bool:
    lowered = path.casefold()
    return lowered.endswith((".tgz", ".tar.gz", ".whl", ".zip"))


def _rewrite_metadata_links(
    body: bytes,
    *,
    content_type: str,
    upstreams: Mapping[str, str],
    gateway_origin: str,
) -> bytes:
    replacements = {
        origin: f"{gateway_origin}/v1/registry/{name}" for name, origin in upstreams.items()
    }
    if "json" in content_type.casefold():
        try:
            document = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return body
        return json.dumps(
            _replace_urls(document, replacements),
            separators=(",", ":"),
        ).encode()
    if "html" in content_type.casefold():
        for origin, replacement in replacements.items():
            body = body.replace(origin.encode(), replacement.encode())
        return body
    return body


def _replace_urls(value: object, replacements: Mapping[str, str]) -> object:
    if isinstance(value, str):
        for origin, replacement in replacements.items():
            if value.startswith(origin):
                return replacement + value[len(origin) :]
        return value
    if isinstance(value, list):
        return [_replace_urls(item, replacements) for item in value]
    if isinstance(value, dict):
        return {key: _replace_urls(item, replacements) for key, item in value.items()}
    return value


def _inspect_archive(path: str, body: bytes, *, limits: object) -> None:
    # Archive inspection APIs accept the concrete limits type; keeping this helper local
    # prevents the HTTP route from exposing archive implementation details.
    from sss_gateway.artifacts import ArchiveLimits

    if not isinstance(limits, ArchiveLimits):
        raise TypeError("invalid archive limits")
    stream = BytesIO(body)
    if path.casefold().endswith((".whl", ".zip")):
        inspect_zip(stream, limits=limits)
    else:
        inspect_tar(stream, limits=limits)
