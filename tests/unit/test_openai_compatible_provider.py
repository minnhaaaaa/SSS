from __future__ import annotations

import logging

import httpx
import pytest
from sss_core import Ecosystem
from sss_worker.jobs.probe import PromptTask
from sss_worker.providers.openai_compatible import OpenAICompatibleProvider


@pytest.mark.asyncio
async def test_provider_records_exact_model_and_hashes_without_logging_body(caplog) -> None:  # type: ignore[no-untyped-def]
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer model-secret"
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "Use novel-lib"}}]}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            base_url="http://model.internal",
            token="model-secret",
            model_id="local-code-model",
            timeout_seconds=5,
            max_response_bytes=1024,
            client=client,
        )
        with caplog.at_level(logging.DEBUG):
            result = await provider.complete(
                PromptTask.create("task-1", "code", Ecosystem.PYPI, "recommend a package")
            )

    assert result.model_id == "local-code-model"
    assert len(result.response_sha256) == 64
    assert "Use novel-lib" not in caplog.text
    assert "model-secret" not in caplog.text


@pytest.mark.asyncio
async def test_provider_retries_transient_status_without_leaking_body(caplog) -> None:  # type: ignore[no-untyped-def]
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, text="sensitive upstream body")
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "npm add safe-lib"}}]}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            base_url="http://model.internal",
            token="model-secret",
            model_id="local-code-model",
            timeout_seconds=5,
            max_response_bytes=1024,
            retry_attempts=2,
            client=client,
        )
        result = await provider.complete(
            PromptTask.create("task-1", "code", Ecosystem.NPM, "recommend an npm package")
        )

    assert calls == 2
    assert result.text == "npm add safe-lib"
    assert "sensitive upstream body" not in caplog.text


@pytest.mark.asyncio
async def test_provider_rejects_oversized_body() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * 101)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            base_url="http://model.internal",
            token="secret",
            model_id="model",
            timeout_seconds=5,
            max_response_bytes=100,
            client=client,
        )
        with pytest.raises(ValueError, match="byte limit"):
            await provider.complete(
                PromptTask.create("task-1", "code", Ecosystem.NPM, "npm package")
            )
