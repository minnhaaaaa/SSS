from __future__ import annotations

from sss_worker.providers.base import ProviderResponse


class ReplayProvider:
    def __init__(
        self,
        *,
        provider: str,
        model_id: str,
        parameters: dict[str, object],
        responses: dict[str, str],
    ) -> None:
        self._provider = provider
        self._model_id = model_id
        self._parameters = parameters.copy()
        self._responses = responses.copy()

    async def generate(self, task_id: str, prompt: str) -> ProviderResponse:
        del prompt
        return ProviderResponse(
            provider=self._provider,
            model_id=self._model_id,
            parameters=self._parameters.copy(),
            text=self._responses[task_id],
        )
