from __future__ import annotations

import httpx
from sss_cli.doctor import check_http_service


def _client(handler: httpx.MockTransport) -> httpx.Client:
    return httpx.Client(transport=handler)


def test_http_service_requires_semantic_health_payload() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"status": "starting"}, request=request)
    )
    with _client(transport) as client:
        result = check_http_service("api", "https://api.example.test/", client=client)

    assert not result.healthy
    assert result.detail == "invalid health response"


def test_http_service_accepts_ok_health_payload() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"status": "ok"}, request=request)
    )
    with _client(transport) as client:
        result = check_http_service("api", "https://api.example.test/", client=client)

    assert result.healthy
    assert result.detail == "HTTP 200"


def test_http_service_reports_invalid_json_as_unhealthy() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, text="not-json", request=request)
    )
    with _client(transport) as client:
        result = check_http_service("api", "https://api.example.test", client=client)

    assert not result.healthy
