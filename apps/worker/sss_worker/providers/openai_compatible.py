"""Bounded OpenAI-compatible chat-completion provider."""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass

import httpx
from sss_core import Ecosystem

from sss_worker.jobs.probe import PromptTask
from sss_worker.providers.base import ProviderResponse


@dataclass(frozen=True, slots=True)
class CompletionResult:
    provider: str
    model_id: str
    text: str
    response_sha256: str


class OpenAICompatibleProvider:
    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        model_id: str,
        timeout_seconds: float,
        max_response_bytes: int,
        retry_attempts: int = 3,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._url = f"{base_url.rstrip('/')}/v1/chat/completions"
        self._token = token
        self._model_id = model_id
        self._timeout = timeout_seconds
        self._max_response_bytes = max_response_bytes
        self._retry_attempts = retry_attempts
        self._client = client

    async def complete(self, task: PromptTask) -> CompletionResult:
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self._timeout)
        try:
            for attempt in range(self._retry_attempts):
                try:
                    response = await client.post(
                        self._url,
                        headers={"Authorization": f"Bearer {self._token}"},
                        json={
                            "model": self._model_id,
                            "messages": [{"role": "user", "content": task.prompt}],
                            "temperature": 0,
                        },
                    )
                    if response.status_code not in {429, 500, 502, 503, 504}:
                        break
                    response.raise_for_status()
                except (httpx.TransportError, httpx.HTTPStatusError):
                    if attempt + 1 == self._retry_attempts:
                        raise
                    await asyncio.sleep(min(2 ** attempt, 4))
            response.raise_for_status()
            if len(response.content) > self._max_response_bytes:
                raise ValueError("model response exceeded configured byte limit")
            document = response.json()
            text = str(document["choices"][0]["message"]["content"])
            return CompletionResult(
                provider="openai-compatible",
                model_id=self._model_id,
                text=text,
                response_sha256=hashlib.sha256(text.encode()).hexdigest(),
            )
        finally:
            if owns_client:
                await client.aclose()

    async def generate(self, task_id: str, prompt: str) -> ProviderResponse:
        task = PromptTask.create(task_id, "runtime", _infer_ecosystem(prompt), prompt)
        result = await self.complete(task)
        return ProviderResponse(
            provider=result.provider,
            model_id=result.model_id,
            parameters={"temperature": 0},
            text=result.text,
        )


def _infer_ecosystem(prompt: str) -> Ecosystem:
    return Ecosystem.NPM if "npm" in prompt.casefold() else Ecosystem.PYPI
